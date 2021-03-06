import os, sys, types
from time import asctime, localtime, time

from CodeGenerator import CodeGenerator
from MiscUtils import AbstractError, StringTypes, mxDateTime, nativeDateTime
from MiddleKit.Core.ObjRefAttr import objRefJoin


class PythonGenerator(CodeGenerator):

	def generate(self, dirname):
		self.requireDir(dirname)
		# @@ 2000-10-17 ce: ACK! Get rid of all these hard coded 'GeneratedPy' strings
		# @@ 2000-10-16 ce: should delete GeneratedPy/
		self.requireDir(os.path.join(dirname, 'GeneratedPy'))
		self.writeInfoFile(os.path.join(dirname, 'GeneratedPy', 'Info.text'))
		self._model.writePy(self, dirname)


class Model:

	def writePy(self, generator, dirname):
		self._klasses.assignClassIds(generator)

		if self.hasSetting('Package'):
			filename = os.path.join(dirname, '__init__.py')
			if not os.path.exists(filename):
				open(filename, 'w').write('#')

		for klass in self._allKlassesInOrder:
			filename = os.path.join(dirname, klass.name() + '.py')
			klass.writePyStubIfNeeded(generator, filename)

			filename = os.path.join(dirname, 'GeneratedPy', 'Gen' + klass.name() + '.py')
			klass.writePy(generator, filename)

		filename = os.path.join(dirname, 'GeneratedPy', '__init__.py')
		open(filename, 'w').write('# __init__.py\n')


class ModelObject:

	def writePy(self, generator, out=sys.stdout):
		""" Writes the Python code to define a table for the class. The target can be a file or a filename. """
		if type(out) in StringTypes:
			out = open(out, 'w')
			close = 1
		else:
			close = 0
		self._writePy(generator, out)
		if close:
			out.close()


class Klass:

	def writePyStubIfNeeded(self, generator, filename):
		if not os.path.exists(filename):
			# Grab values for use in writing file
			basename = os.path.basename(filename)
			name = self.name()
			superclassModule = 'GeneratedPy.Gen' + name
			superclassName = 'Gen' + name

			# Write file
			file = open(filename, 'w')
			file.write(PyStubTemplate % locals())
			file.close()

	def _writePy(self, generator, out):
		self._pyGenerator = generator
		self._pyOut = out
		self.writePyFileDocString()
		self.writePyAttrCaches()
		self.writePyImports()
		self.writePyClassDef()

	def writePyFileDocString(self):
		wr = self._pyOut.write
		out = self._pyOut
		wr("""'''\n""")
		wr('Gen%s.py\n' % self.name())
		#wr('%s\n' % asctime(localtime(time())))
		wr('Generated by MiddleKit.\n') # @@ 2000-10-01 ce: Put the version number here
		wr("""'''\n""")

	def writePyAttrCaches(self):

		wr = self._pyOut.write
		wr('''
# MK attribute caches for setFoo() methods
''')
		for attr in self.allAttrs():
			wr('_%sAttr = None\n' % attr.name())
		wr('\n')

	def writePyImports(self):
		wr = self._pyOut.write
		wr('''
import types
try:
	from types import StringTypes
except ImportError: # fallback for Python < 2.2
	from types import StringType, UnicodeType
	StringTypes = (StringType, UnicodeType)
try:
	from decimal import Decimal
except ImportError: # fallback for Python < 2.4
	Decimal = float
''')
		if nativeDateTime:
			if nativeDateTime.__name__ == 'datetime':
				wr('import datetime\n')
			else:
				wr('import %s as datetime\n' % nativeDateTime.__name__)
		if mxDateTime:
			wr('import %s as mxDateTime\n' % mxDateTime.__name__)
		supername = self.supername()
		if supername == 'MiddleObject':
			wr('\n\nfrom MiddleKit.Run.MiddleObject import MiddleObject\n')
		else:
			pkg = self._klasses._model.setting('Package', '')
			if pkg:
				pkg += '.'
			# backPath = repr('../' * (pkg.count('.') + 1))
			backPath = 'dirname(__file__)'
			for i in xrange(pkg.count('.') + 1):
				backPath = 'dirname(%s)' % backPath
			wr('''\
import sys
from MiddleKit.Run.MiddleObject import MiddleObject
from os.path import dirname
sys.path.insert(0, %(backPath)s)
from %(pkg)s%(supername)s import %(supername)s
del sys.path[0]

''' % locals())

	def writePyClassDef(self):
		wr = self._pyOut.write
		wr('\n\nclass Gen%s(%s):\n' % (self.name(), self.supername()))
		self.writePyInit()
		self.writePyReadStoreData()
		self.writePyAccessors()
		wr('\n')

	def maxAttrNameLen(self):
		maxLen = 0
		for attr in self.attrs():
			if maxLen < len(attr.name()):
				maxLen = len(attr.name())
		return maxLen

	def writePyInit(self):
		wr = self._pyOut.write
		wr('\n\tdef __init__(self):\n')
		wr('\t\t%s.__init__(self)\n' % self.supername())
		maxLen = self.maxAttrNameLen()
		for attr in self.attrs():
			name = attr.name().ljust(maxLen)
			wr('\t\tself._%s = %r\n' % (name, attr.defaultValue()))
		wr('\n')

	def writePyReadStoreData(self):
		wr = self._pyOut.write
		statements = [attr.pyReadStoreDataStatement() for attr in self.attrs()]
		statements = [s for s in statements if s]
		if statements:
			wr('''
	def readStoreData(self, store, row):
		if not self._mk_inStore:
''')
			for s in statements:
				wr(s)
			wr('\t\t%s.readStoreData(self, store, row)\n\n' % self.supername())

	def writePyAccessors(self):
		""" Write Python accessors for attributes simply by asking each one to do so. """
		out = self._pyOut
		for attr in self.attrs():
			attr.writePyAccessors(out)


class Attr:

	def defaultValue(self):
		""" Returns the default value as a legal Pythonic value. """
		if self.has_key('Default'):
			default = self['Default']
			if type(default) in StringTypes:
				default = default.strip()
			if not default:
				return None
			else:
				return self.stringToValue(default)
		else:
			return None

	def stringToValue(self, string):
		# @@ 2000-11-25 ce: consider moving this to Core
		# @@ 2000-11-25 ce: also, this might be usable in the store
		"""
		Returns a bona fide Python value given a string. Invokers should never pass None or blank strings.
		Used by at least defaultValue().
		Subclass responsibility.
		"""
		raise AbstractError, self.__class__

	def pyReadStoreDataStatement(self):
		return None

	def writePyAccessors(self, out):
		self.writePyGet(out)
		self.writePySet(out)
		if self.setting('AccessorStyle', 'methods') == 'properties':
			out.write('\n\n\t%s = property(%s, %s)\n\n' % (self.name(), self.pyGetName(), self.pySetName()))

	def writePyGet(self, out):
		out.write('''
	def %s(self):
		return self._%s
''' % (self.pyGetName(), self.name()))

	def writePySet(self, out):
		name = self.name()
		pySetName = self.pySetName()
		capName = name[0].upper() + name[1:]
		values = locals()
		out.write('\n\tdef %(pySetName)s(self, value):\n' % values)
		self.writePySetChecks(out)
		self.writePySetAssignment(out.write, name)

	def writePySetAssignment(self, write, name):
		write('''
		# set the attribute
		origValue = self._%(name)s
		self._%(name)s = value

		# MiddleKit machinery
		if not self._mk_initing and self._mk_serialNum>0 and value is not origValue:
			global _%(name)sAttr
			if _%(name)sAttr is None:
				_%(name)sAttr = self.klass().lookupAttr('%(name)s')
				if not _%(name)sAttr.shouldRegisterChanges():
					_%(name)sAttr = 0
			if _%(name)sAttr:
				# Record that it has been changed
				self._mk_changed = 1
				if self._mk_changedAttrs is None:
					self._mk_changedAttrs = {} # maps name to attribute
				self._mk_changedAttrs['%(name)s'] = _%(name)sAttr  # changedAttrs is a set
				# Tell ObjectStore it happened
				self._mk_store.objectChanged(self)
''' % {'name': name})

	def writePySetChecks(self, out):
		if self.isRequired():
			out.write('\t\tassert value is not None\n')


PyStubTemplate = """\
'''
%(basename)s
'''


from %(superclassModule)s import %(superclassName)s


class %(name)s(%(superclassName)s):

	def __init__(self):
		%(superclassName)s.__init__(self)
"""


class BoolAttr:

	def stringToValue(self, string):
		try:
			string = string.upper()
		except:
			pass
		if string in (True, 'TRUE', 'YES', '1', '1.0', 1, 1.0):
			value = 1
		elif string in (False, 'FALSE', 'NO', '0', '0.0', 0, 0.0):
			value = 0
		else:
			value = int(string)
		assert value == 0 or value == 1, value
		return value

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
			if not isinstance(value, types.IntType):
				raise TypeError, 'expecting bool or int for bool, but got value %r of type %r instead' % (value, type(value))
			if value not in (True, False, 1, 0):
				raise ValueError, 'expecting True, False, 1 or 0 for bool, but got %s instead' % value
''')


class IntAttr:

	def stringToValue(self, string):
		return int(string)

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
			if isinstance(value, types.LongType):
				value = int(value)
				if isinstance(value, types.LongType): # happens in Python 2.3
					raise OverflowError, value
			elif not isinstance(value, types.IntType):
				raise TypeError, 'expecting int type, but got value %r of type %r instead' % (value, type(value))
''')


class LongAttr:

	def stringToValue(self, string):
		return long(string)

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
			if isinstance(value, types.IntType):
				value = long(value)
			elif not isinstance(value, types.LongType):
				raise TypeError, 'expecting long type, but got value %r of type %r instead' % (value, type(value))
''')


class FloatAttr:

	def stringToValue(self, string):
		return float(string)

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
			if isinstance(value, (types.IntType, types.LongType)):
				value = float(value)
			elif not isinstance(value, types.FloatType):
				raise TypeError, 'expecting float type, but got value %r of type %r instead' % (value, type(value))
''')


class DecimalAttr:

	def stringToValue(self, string):
		return float(string)

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
			if isinstance(value, (types.IntType, types.LongType)):
				value = float(value)
			elif isinstance(value, types.FloatType):
				value = Decimal(str(value))
			elif not isinstance(value, Decimal):
				raise TypeError, 'expecting decimal type, but got value %r of type %r instead' % (value, type(value))
''')


class StringAttr:

	def stringToValue(self, string):
		return string

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
			if not isinstance(value, types.StringType):
				raise TypeError, 'expecting string type, but got value %r of type %r instead' % (value, type(value))
''')


class EnumAttr:

	def stringToValue(self, string):
		if self.usesExternalSQLEnums():
			return self.intValueForString(string)
		else:
			return string

	def writePyAccessors(self, out):
		Attr.writePyAccessors.im_func(self, out)
		if self.setting('ExternalEnumsSQLNames')['Enable']:
			name = self.name()
			getName = self.pyGetName()
			out.write('''
	def %(getName)sString(self):
		global _%(name)sAttr
		if _%(name)sAttr is None:
			_%(name)sAttr = self.klass().lookupAttr('%(name)s')
		return _%(name)sAttr.enums()[self._%(name)s]
''' % locals())
			if self.setting('AccessorStyle', 'methods') == 'properties':
				out.write('\n\n\t%(name)sString = property(%(getName)sString, "Returns the string form of %(name)s (instead of the integer value).")\n\n' % locals())

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		global _%(name)sAttr
		if _%(name)sAttr is None:
			_%(name)sAttr = self.klass().lookupAttr('%(name)s')
''' % {'name': self.name()})
		if self.usesExternalSQLEnums():
			out.write('''
		if value is not None:
			if isinstance(value, types.StringType):
				try:
					value = _%(name)sAttr.intValueForString(value)
				except KeyError:
					raise ValueError, 'expecting one of %%r, but got %%r instead' %% (_%(name)sAttr.enums(), value)
			elif not isinstance(value, (types.IntType, types.LongType)):
				raise TypeError, 'expecting int type for enum, but got value %%r of type %%r instead' %% (value, type(value))
			if not _%(name)sAttr.hasEnum(value):
				raise ValueError, 'expecting one of %%r, but got %%r instead' %% (_%(name)sAttr.enums(), value)
''' % {'name': self.name()})
		else:
			out.write('''
		if value is not None:
			if not isinstance(value, types.StringType):
				raise TypeError, 'expecting string type for enum, but got value %%r of type %%r instead' %% (value, type(value))
			attr = self.klass().lookupAttr('%s')
			if not attr.hasEnum(value):
				raise ValueError, 'expecting one of %%r, but got %%r instead' %% (attr.enums(), value)
''' % self.name())
			# @@ 2001-07-11 ce: could optimize above code

	def writePySetAssignment(self, write, name):
		write('''
		# set the attribute
		origValue = self._%(name)s
		self._%(name)s = value

		# MiddleKit machinery
		if not self._mk_initing and self._mk_serialNum>0 and value is not origValue:
			# Record that it has been changed
			self._mk_changed = 1
			if self._mk_changedAttrs is None:
				self._mk_changedAttrs = {} # maps name to attribute
			self._mk_changedAttrs['%(name)s'] = _%(name)sAttr  # changedAttrs is a set
			# Tell ObjectStore it happened
			self._mk_store.objectChanged(self)
''' % {'name': name})


	## Settings ##

	def usesExternalSQLEnums(self):
		# @@ 2004-02-25 ce: seems like this method and its use should be pushed down to SQLPythonGenerator.py
		flag = getattr(self, '_usesExternalSQLEnums', None)
		if flag is None:
			flag = self.model().usesExternalSQLEnums()
			self._usesExternalSQLEnums = flag
		return flag


class AnyDateTimeAttr:

	def nativeDateTimeTypeName(self):
		raise AbstractError, self.__class__

	def mxDateTimeTypeName(self):
		raise AbstractError, self.__class__

	def writePySetChecks(self, out):
		Attr.writePySetChecks.im_func(self, out)
		out.write('''\
		if value is not None:
''')
		if mxDateTime:
			# I don't see anything for parsing in Python's datetime module, so only
			# mx.DateTime users get this convenience (which has been in MiddleKit
			# for years):
			out.write('''\
			if type(value) in StringTypes:
				value = mxDateTime.%s(value)
''' % self.mxDateTimeTypeName().replace('Type', 'From'))
		dateTimeTypes = []
		if nativeDateTime:
			# Python's datetime types
			typeNames = self.nativeDateTimeTypeName()
			if not isinstance(typeNames, tuple):
				typeNames = (typeNames,)
			for typeName in typeNames:
				dateTimeTypes.append('datetime.' + typeName)
		if mxDateTime:
			# egenix's mx.DateTime types
			typeNames = self.mxDateTimeTypeName()
			if not isinstance(typeNames, tuple):
				typeNames = (typeNames,)
			for typeName in typeNames:
				dateTimeTypes.append('mxDateTime.' + typeName)
		assert dateTimeTypes
		if len(dateTimeTypes) > 1:
			dateTimeTypes = '(' + ', '.join(dateTimeTypes) + ')'
		else:
			dateTimeTypes = dateTimeTypes[0]
		out.write('''
			if not isinstance(value, %s):
				raise TypeError, 'expecting %s type (e.g., %s), but got value %%r of type %%r instead' %% (value, type(value))
''' % (dateTimeTypes, self['Type'], dateTimeTypes))

	def writePyGetAsMXDateTime(self, out):
		if nativeDateTime and mxDateTime and self.setting('ReturnMXDateTimes', False):
			dateTimeTypes = []
			typeNames = self.nativeDateTimeTypeName()
			if not isinstance(typeNames, tuple):
				typeNames = (typeNames,)
			for typeName in typeNames:
				dateTimeTypes.append('datetime.' + typeName)
			dateTimeTypes = '(' + ', '.join(dateTimeTypes) + ')'
			out.write('''
	def %s(self):
		if isinstance(self._%s, %s):
			self._%s = mxDateTime.mktime(self._%s.timetuple())
		return self._%s
	''' % (self.pyGetName(), self.name(), dateTimeTypes, self.name(), self.name(), self.name()))
		else:
			out.write('''
	def %s(self):
		return self._%s
	''' % (self.pyGetName(), self.name()))


class DateAttr:

	def nativeDateTimeTypeName(self):
		return 'date'

	def mxDateTimeTypeName(self):
		return 'DateTimeType'

	def writePyGet(self, out):
		self.writePyGetAsMXDateTime(out)


class TimeAttr:

	def nativeDateTimeTypeName(self):
		return ('time', 'timedelta')

	def mxDateTimeTypeName(self):
		return 'DateTimeDeltaType'

	def writePySetChecks(self, out):
		# additional check to also allow DateTime instances.  This is what
		# comes back from the database for 'time' columns using PostgresSQL
		# and the psycopg adapter.
		if mxDateTime:
			out.write('''\
		if isinstance(value, mxDateTime.DateTimeType):
			value = mxDateTime.DateTimeDeltaFrom(value.time)
''')
		TimeAttr.mixInSuperWritePySetChecks(self, out)


class DateTimeAttr:

	def nativeDateTimeTypeName(self):
		return 'datetime'

	def mxDateTimeTypeName(self):
		return 'DateTimeType'

	def writePyGet(self, out):
		self.writePyGetAsMXDateTime(out)


class ObjRefAttr:

	def stringToValue(self, string):
		parts = string.split('.')
		if len(parts) == 2:
			className = parts[0]
			objSerialNum = parts[1]
		else:
			className = self.targetClassName()
			objSerialNum = string
		klass = self.klass().klasses()._model.klass(className)
		klassId = klass.id()
		objRef = objRefJoin(klassId, int(objSerialNum))
		return objRef

	def writePySet(self, out):
		name = self.name()
		pySetName = self.pySetName()
		targetClassName = self.targetClassName()
		package = self.setting('Package', '')
		if package:
			package += '.'
		if self.isRequired():
			reqAssert = 'assert value is not None'
		else:
			reqAssert = ''
		out.write('''
	def %(pySetName)s(self, value):
		%(reqAssert)s
		if value is not None and not isinstance(value, types.LongType):
			if not isinstance(value, MiddleObject):
				raise TypeError, 'expecting a MiddleObject, but got value %%r of type %%r instead' %% (value, type(value))
			from %(package)s%(targetClassName)s import %(targetClassName)s
			if not isinstance(value, %(targetClassName)s):
				raise TypeError, 'expecting %(targetClassName)s, but got value %%r of type %%r instead' %% (value, type(value))
''' % locals())
		self.writePySetAssignment(out.write, name)


class ListAttr:

	def defaultValue(self):
		""" Returns the default value as a legal Pythonic value. """
		assert not self.get('Default', 0), 'Cannot have default values for lists.'
		return []

	def pyReadStoreDataStatement(self):
		# Set the lists to None on the very first read from the store
		# so the list get methods will fetch the lists from the store.
		return '\t\t\tself._%s = None\n' % self.name()

	def writePyAccessors(self, out):
		# Create various name values that are needed in code generation
		name = self.name()
		pyGetName = self.pyGetName()
		pySetName = self.pySetName()
		capName = name[0].upper() + name[1:]
		sourceClassName = self.klass().name()
		targetClassName = self.className()
		backRefAttrName = self.backRefAttrName()
		upperBackRefAttrName = backRefAttrName[0].upper() + backRefAttrName[1:]
		package = self.setting('Package', '')
		if package:
			package += '.'
		names = locals()

		# Invoke various code gen methods with the names
		self.writePyGet(out, names)
		self.writePyAddTo(out, names)

	def writePyGet(self, out, names):
		""" Subclass responsibility. """
		raise AbstractError

	def writePySet(self, out, names=None):
		""" Raises an exception in order to ensure that our inherited "PySet" code generation is used. """
		raise AssertionError, 'Lists do not have a set method.'

	def writePyAddTo(self, out, names):
		names['getParens'] = self.setting('AccessorStyle', 'methods') == 'methods' and '()' or ''
		out.write('''
	def addTo%(capName)s(self, value):
		assert value is not None
		from %(package)s%(targetClassName)s import %(targetClassName)s
		assert isinstance(value, %(targetClassName)s)
		assert value.%(backRefAttrName)s%(getParens)s is None
		self.%(pyGetName)s().append(value)
		value._set('%(backRefAttrName)s', self)
		store = self.store()
		if value.serialNum() == 0 and self.isInStore():
			store.addObject(value)
''' % names)
		del names['getParens']
