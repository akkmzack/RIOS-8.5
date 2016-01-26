# -*- python -*-
#
# (C) Copyright 2003-2009 Riverbed Technology, Inc.  
# All rights reserved. Confidential.
#
"""Interval - Classes related to intervals"""

#------------------------------------------------------------------------------
import bisect
from bisect import bisect_left, bisect_right

# Set to True to print debugging information.
# Uncomment one of these.
_Interval_debug = False
#_Interval_debug = True


#------------------------------------------------------------------------------
# Bucket stat functions

def get_bucket_count():
    # from rbt/misc/bucketstats.h
    return 33

# Bucket divisions (from rbt/misc/bucketstats.h)
def get_buckets():
    # Buckets 0..32 count
    # n in [0], [1], [2], [3,4], [5,8], ..., [2^29+1,2^30], [2^30+1,inf)
    buckets = [[0,0], [1,1], [2,2]]
    for i in range(3, get_bucket_count()):
        buckets.append([(1 << (i-2)) + 1, 1 << (i - 1)])

    return buckets

def get_bucket_divisions():
    buckets = get_buckets()
    divs = ["0", "1", "2"]
    for i in range(3, len(buckets)):
        n = buckets[i][0];
        m = buckets[i][1];
        divs.append("%s-%s" % (to_unit(n), to_unit(m)))

    return divs

# Which bucket contains value?
def get_bucket_index(value):
    buckets = get_buckets()
    for idx, bucket in enumerate(buckets):
        if (bucket[0] <= value) and (value <= bucket[1]):
            return idx
    return len(buckets) - 1

def get_bucket_from_index(index):
    buckets = get_buckets()
    return buckets[index]

#------------------------------------------------------------------------------
class Interval(object):
    """Contains a range, like BlockSeqDesc in prefetch."""
    def __init__(self, start = 0, num = None):
        """Initialize to:
        * Interval
        * start, num
        * start: num defaults to 1
        * or: start defaults to 0, num defaults to 1."""
        if isinstance(start, Interval):
            if num != None:
                return NotImplemented
            num = start.num
            start = start.start
        elif num == None:
            num = 1
        self.start = start
        self.num = num

    # Access functions.
    def get_start(self):
        return self.start

    def get_num(self):
        return self.num

    # Computed access function
    def get_end(self):
        if self.num != 0:
            return self.start + (self.num - 1)
        else:
            return 0
        
    # Test functions.
    def is_adjacent(self, value):
        """True if value is adjacent to the end."""
        if isinstance(value, Interval):
            result = ((self.num > 0) and (value.num > 0) and
                      ((self.get_end() + 1) == value.start))
        else:
            result = ((self.get_end() + 1) == value)
        if _Interval_debug:
            print "is_adjacent", "self:", self, "value:", value, \
                  "returns:", result
        return result

    def is_in_range(self, value):
        """True if value is contained within self."""
        if isinstance(value, Interval):
            result = ((self.num > 0) and (value.num > 0) and
                      (self.start <= value.start) and
                      (value.get_end() <= self.get_end()))
        else:
            result = ((self.num > 0) and (self.start <= value) and
                      (value <= self.get_end()))
        if _Interval_debug:
            print "is_in_range", "self:", self, "value:", value, \
                  "returns:", result
        return result

    def is_before(self, value):
        """True if value is before self."""
        if isinstance(value, Interval):
            result = ((self.num > 0) and (value.num > 0) and
                      (value.get_end() < self.start))
        else:
            result = ((self.num > 0) and (value < self.start))
        if _Interval_debug:
            print "is_before", "self:", self, "value:", value, \
                  "returns:", result
        return result

    # Modify functions
    def advance(self, value):
        """Advance start of self by value reducing num."""
        orig_value = value
        if value > self.num:
            value = self.num
        result = Interval(self.start + value, self.num - value)
        if _Interval_debug:
            print "advance", "self:", self, "value:", orig_value, \
                  "returns:", result
        return result

    def next(self, value = None):
        """Next interval, i.e. increase self.start by value, default self.num."""
        if value == None:
            value = self.num
        next_interval = Interval.advance(self, value)
        next_interval.num = self.num
        return next_interval

    # Lookup functions.
    def find(self, to_find, include_gaps = True):
        """Return subset of self for interval TO_FIND, or None.
        Return gap as an interval if include_gaps, otherwise None."""
        if _Interval_debug:
            print "Interval.find(self: %s, to_find: %s, include_gaps: %s)" % (
                str(self), str(to_find), str(include_gaps))
        if to_find.start < self.start:
            # Gap between to_find and self
            gap_num = self.start - to_find.start
            if gap_num > to_find.num:
                gap_num = to_find.num
            if include_gaps:
                gap = Interval(to_find.start, gap_num)
                if _Interval_debug:
                    print "Interval.find: Gap with include_gaps:" \
                          " returns: %s" % str(gap)
                return gap
            to_find = Interval.advance(to_find, gap_num)
            if to_find.num == 0:
                if _Interval_debug:
                    print "Interval.find: Gap without include_gaps:" \
                          " returns: None"
                return None
        if to_find.start <= self.get_end():
            # Start of to_find is within self
            self_advance = Interval.advance(self,
                                            to_find.start - self.start)
            self_num = min(self_advance.num, to_find.num)
            self_advance.num = self_num
            if _Interval_debug:
                print "Interval.find: Start within:" \
                      " returns: %s" % str(self_advance)
            return self_advance
        # Start of to_find is after self
        if _Interval_debug:
            print "Interval.find: Start after: returns: None"
        return None

    # Print function.
    def __str__(self):
        return "(%s, %s)" % (str(self.start), str(self.num))

    # Comparison functions
    def __lt__(self, other):
        if _Interval_debug:
            print "Interval.__lt__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        if not isinstance(other, Interval):
            if _Interval_debug:
                print "__lt__ NotImplmented", "self:", self, "other:", other, \
                      "type(self):", type(self), "type(other):", type(other)
            return NotImplemented
        return ((self.get_start() < other.get_start()) or
                ((self.get_start() == other.get_start()) and
                 (self.get_num() < other.get_num())))

    def __eq__(self, other):
        if _Interval_debug:
            print "Interval.__eq__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        if other == None:
            return False
        if not isinstance(other, Interval):
            if _Interval_debug:
                print "__eq__ NotImplmented", "self:", self, "other:", other, \
                      "type(self):", type(self), "type(other):", type(other)
            return NotImplemented
        return ((self.get_start() == other.get_start()) and
                (self.get_num() == other.get_num()))

    def __ne__(self, other):
        if _Interval_debug:
            print "Interval.__ne__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        not_result = Interval.__eq__(self, other)

        if not_result == NotImplemented:
            return NotImplemented

        return not not_result

    def __le__(self, other):
        if _Interval_debug:
            print "Interval.__le__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        not_result = Interval.__lt__(other, self)

        if not_result == NotImplemented:
            return NotImplemented

        return not not_result

    def __gt__(self, other):
        if _Interval_debug:
            print "Interval.__gt__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        return Interval.__lt__(other, self)

    def __ge__(self, other):
        if _Interval_debug:
            print "Interval.__ge__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        not_result = Interval.__lt__(self, other)

        if not_result == NotImplemented:
            return NotImplemented

        return not not_result

#------------------------------------------------------------------------------
def _append_or_extend(all_answers, answer_found):
    len_all_answers = len(all_answers)
    if len_all_answers == 0:
        if _Interval_debug:
            print "all_answers[%d] %s" % (
                len_all_answers, str(answer_found))
        all_answers.append(answer_found)
    elif all_answers[len_all_answers - 1].is_adjacent(answer_found):
        all_answers[len_all_answers - 1].num += answer_found.num
        if _Interval_debug:
            print "all_answers[%d] changed to: %s" % (
                len_all_answers - 1, str(all_answers[len_all_answers - 1]))
    else:
        if _Interval_debug:
            print "all_answers[%d] %s" % (
                len_all_answers, str(answer_found))
        all_answers.append(answer_found)
    if _Interval_debug:
        print

#------------------------------------------------------------------------------
def _find_le(array, x, lo=0, hi=None):
    '''Find rightmost item in array less than or equal to x.
    Return subscript, item.'''
    subscript = bisect_right(array, x, lo, hi)
    if subscript != 0:
        subscript -= 1
        result = array[subscript]
        if _Interval_debug:
            print "_find_le", "len(array):", len(array), "x:", x, \
                  "returns:[%d]" % subscript, result
    else:
        result = None
        if _Interval_debug:
            print "_find_le", "len(array):", len(array), "x:", x, \
                  "returns:", result
    return subscript, result

def _find_ge(array, x, lo=0, hi=None):
    '''Find leftmost item in array greater than or equal to x.
    Return subscript, item.'''
    subscript = bisect_left(array, x, lo, hi)
    len_array = len(array)
    if subscript != len_array:
        result = array[subscript]
        if _Interval_debug:
            print "_find_ge", "len(array):", len_array, "x:", x, \
                  "returns:[%d]" % subscript, result
    else:
        result = None
        if _Interval_debug:
            print "_find_ge", "len(array):", len_array, "x:", x, \
                  "returns:", result
    return subscript, result

#------------------------------------------------------------------------------
class Run(Interval):
    """An Interval on a Whole."""
    def __init__(self, whole, start = None, num = None):
        """Initialize to:
        * Run
        * whole, Interval
        * whole, start, num
        * whole, start: num defaults to 1
        * or whole: start defaults to 0, num defaults to 1."""
        if isinstance(whole, Run):
            if (start != None) or (num != None):
                return NotImplemented
            start = whole.start
            num = whole.num
            whole = whole.whole
        elif isinstance(start, Interval):
            if num != None:
                return NotImplemented
            num = start.num
            start = start.start
        else:
            if start == None:
                start = 0
            if num == None:
                num = 1
        Interval.__init__(self, start, num)
        self.whole = whole

    # Access functions.
    def get_whole(self):
        return self.whole

    # XXX This creates a new Interval.  It should return the Base class from
    # the instance.
    def get_interval(self):
        return Interval(self.start, self.num)

    # Test functions.
    def is_adjacent(self, other):
        if isinstance(other, Run):
            if (other.whole == self.whole):
                result = Interval.is_adjacent(self, other)
            else:
                result = False
        else:
            result = Interval.is_adjacent(self, other)
        if _Interval_debug:
            print "Run.is_adjacent", "self:", self, "other:", other, \
                  "returns:", result
        return result

    def is_before(self, other):
        if isinstance(other, Run):
            if (other.whole < self.whole):
                result = True
            elif (other.whole == self.whole):
                result = Interval.is_before(self, other)
            else:
                result = False
        else:
            result = Interval.is_before(self, other)
        if _Interval_debug:
            print "Run.is_before", "self:", self, "other:", other, \
                  "returns:", result
        return result

    def is_in_range(self, other):
        if isinstance(other, Run):
            if (other.whole == self.whole):
                result = Interval.is_in_range(self, other)
            else:
                result = False
        else:
            result = Interval.is_in_range(self, other)
        if _Interval_debug:
            print "Run.is_in_range", "self:", self, "other:", other, \
                  "returns:", result
        return result

    def value_is_in_range(self, whole, value):
        result = ((whole == self.whole) and Interval.is_in_range(self, value))
        if _Interval_debug:
            print "Run.value_is_in_range", "self:", self, \
                  "whole:", whole, "value:", value, "returns:", result
        return result

    def value_is_before(self, whole, value):
        result = ((whole < self.whole) or
                  ((whole == self.whole) and
                   self.is_before(value)))
        if _Interval_debug:
            print "Run.value_is_before", "self:", self, \
                  "whole:", whole, "value:", value, "returns:", result
        return result

    # Modify functions
    def advance(self, value):
        """Advance start of self by value reducing num."""
        new_interval = Interval.advance(self, value)
        result = Run(self.whole, new_interval.start, new_interval.num)
        if _Interval_debug:
            print "Run.advance", "self:", self, "value:", value, \
                  "returns:", result
        return result

    def next(self, value = None):
        """Next Run, i.e. increase start by value, default self.num."""
        if value == None:
            value = self.num
        next_run = Run.advance(self, value)
        next_run.num = self.num
        return next_run

    # Lookup functions.
    def find(self, to_find, include_gaps = True):
        """Return subset of self for Run TO_FIND, or None.
        Return wrong Whole as NotImplemented if include_gaps, otherwise None.
        Return gap as Run if include_gaps, otherwise None."""
        if _Interval_debug:
            print "Run.find(self: %s, to_find: %s, include_gaps: %s)" % (
                str(self), str(to_find), str(include_gaps))
        if isinstance(to_find, Run):
            if self.whole != to_find.whole:
                # Wrong Whole
                if include_gaps:
                    return NotImplemented
                else:
                    return None
        result = Interval.find(self, to_find, include_gaps)
        if result == None:
            return result
        return Run(self.whole, result)

    # Print function.
    def __str__(self):
        interval = Interval(self.start, self.num)
        return "Run: '%s' %s" % (self.whole, str(interval))

    # Comparison functions
    def __lt__(self, other):
        if _Interval_debug:
            print "Run.__lt__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        if isinstance(other, Run):
            return ((self.whole < other.whole) or
                    ((self.whole == other.whole) and
                     Interval.__lt__(self, other)))

        if isinstance(other, Interval):
            return Interval.__lt__(self, other)

        if _Interval_debug:
            print "Run.__lt__ NotImplmented", \
                  "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        return NotImplemented

    def __eq__(self, other):
        if _Interval_debug:
            print "Run.__eq__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        if other == None:
            return False

        if isinstance(other, Run):
            return ((self.whole == other.whole) and
                     Interval.__eq__(self, other))

        if isinstance(other, Interval):
            return Interval.__eq__(self, other)

        if _Interval_debug:
            print "Run.__eq__ NotImplmented", \
                  "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        return NotImplemented

    def __ne__(self, other):
        if _Interval_debug:
            print "Run.__ne__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        not_result = Run.__eq__(self, other)

        if not_result == NotImplemented:
            return NotImplemented

        return not not_result

    def __le__(self, other):
        if _Interval_debug:
            print "Run.__le__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        not_result = Run.__lt__(other, self)

        if not_result == NotImplemented:
            return NotImplemented

        return not not_result

    def __gt__(self, other):
        if _Interval_debug:
            print "Run.__gt__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        return Run.__lt__(other, self)

    def __ge__(self, other):
        if _Interval_debug:
            print "Run.__ge__", "self:", self, "other:", other, \
                  "type(self):", type(self), "type(other):", type(other)
        not_result = Run.__lt__(self, other)

        if not_result == NotImplemented:
            return NotImplemented

        return not not_result

#------------------------------------------------------------------------------
class RunList(list):
    """A list of Interval."""
    def __init__(self, interval = None, num = None):
        """Initialize to:
        * RunList: A copy of RunList
        * Interval: A list of Interval
        * start, num: A list of Interval(start, num)
        * start: A list of Interval(start, 1)
        * or: An empty list."""
        if isinstance(interval, RunList):
            if num != None:
                return NotImplemented
            a_list = interval[:]
        elif isinstance(interval, Interval):
            if num != None:
                return NotImplemented
            a_list = [ interval ]
        elif interval != None:
            if num == None:
                num = 1
            interval = Interval(interval, num)
            a_list = [ interval ]
        else:
            if num != None:
                return NotImplemented
            a_list = []
        list.__init__( [] )
        list.extend(self, a_list)

    # Lookup functions.
    def find(self, run, make_gap = None):
        """Return RunList for Run run in self."""
        if _Interval_debug:
            print "RunList.find(%d, run %s, %s)" % (
                len(self), str(run), str(make_gap != None))
        all_runs = RunList()
        len_self = len(self)
        if len_self == 0:
            return all_runs
        while run.num > 0:
            subscript, run_from_list = _find_le(self, run, 0, None)
            if run_from_list == None:
                # self[0] > run.  Use self[0]
                subscript = 0
                run_from_list = self[0]
            elif not run_from_list.value_is_in_range(run.whole,
                                                     run.get_start()):
                # self[subscript] < run, Use self[subscript + 1]
                subscript += 1
                if subscript == len_self:
                    run_from_list = None
                else:
                    run_from_list = self[subscript]
            # else self[subscript] == run, use it.
            if run_from_list == None:
                if make_gap != None:
                    run_found = make_gap(run)
                    if _Interval_debug:
                        print "RunList.find:", \
                              "Insert gap for not found:", run_found
                    _append_or_extend(all_runs, run_found)
                break
            run_found = run_from_list.find(run, make_gap)
            if run_found == None:
                break
            if _Interval_debug:
                if run_found.filehandle == None:
                    print "RunList.find:", \
                          "Insert gap before run:", run_found
                else:
                    print "RunList.find:", \
                          "Insert run:", run_found
            _append_or_extend(all_runs, run_found)
            run = run.advance(
                (1 + run_found.get_end()) - run.start)
            if run.num == 0:
                break
            if run_found.filehandle == None:
                # Inserted gap before run, now insert run without calling
                # RunList.find again.
                run_found = run_from_list.find(run, make_gap)
                if _Interval_debug:
                    print "RunList.find:", \
                          "Insert run after gap:", run_found
                _append_or_extend(all_runs, run_found)
                run = run.advance(run_found.num)
        return all_runs

#------------------------------------------------------------------------------
