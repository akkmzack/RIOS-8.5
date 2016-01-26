/* Copyright 2012, Riverbed Technology Inc.  All rights reserved.
 *
 * Code that must be run after including jQuery to ensure interoperability.
 * Author: Kyle Getz
 *
 * By default, jQuery defines $ for its own uses, but this conflicts with our
 * use of $.  Lucky for us, jQuery will relinquish their definition of $ if you
 * ask nicely.
 *
 * More info: http://api.jquery.com/jQuery.noConflict/
 */

jQuery.noConflict();
