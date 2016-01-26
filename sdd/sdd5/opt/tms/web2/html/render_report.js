// $Id: render_report.js 105806 2013-06-03 20:50:02Z yzhang $
//
// This script directs PhantomJs in order to render a report.

if (phantom.args.length != 2) {
    console.log('Usage: render_report.js <generator-URL> <output-filename>');
    phantom.exit();
}

var initial_delay_ms = 1000;
var iterative_delay_ms = 1000;
var iteration_limit = 300;

var address = phantom.args[0];
var output = phantom.args[1];

var logout_url = 'http://localhost/mgmt/logout';

// XXX 10/24/12: this might have to change, or be eliminated.
var page = require('webpage').create();
page.viewportSize = { width: 1000, height: 600 };

page.onConsoleMessage = function(msg, lineNum, sourceId) {
    console.log('CONSOLE: ' + msg + ' (from line #' + lineNum + ' in "' + sourceId + '")');
};

// Returns an empty string if Highcharts has finished rendering the target
// graph; otherwise, a string describing the rendering status is returned.

function get_rendering_status()
{
    var rendering_code = page.evaluate(function() {
        // Check in order the cases the document is a tsc, pie chart or bubble chart.
        // For each of them, check until the chart has been rendered.

        // This function testing will be used for each test of tsc, pie chart, and bubble chart
        function testingElement(el, stringEl){
            var hsc = el._chart;
            if (!hsc) {
                return stringEl + ': no hsc';
            }
            if (!hsc.hasRendered) {
                return stringEl + ': not yet rendered';
            }       
            return '';
        }

        if (!document) {
            return 'no document';
        }
        var tscwc = document.chart;
        if (!tscwc) {
            return 'no hsc';
        }

        var retMsg = '';
        var dictEl = {'tsc':tscwc._tsc, 'pc':tscwc._pc, 'bc':tscwc._bc };
        for (el in dictEl){
            if (dictEl[el]){
                retMsg = testingElement(dictEl[el], el); 
                // We assume that only one chart is used on any page
                if (retMsg == ''){
                    break;
                }
            }
            
        }
        return retMsg;
    });

    return rendering_code;
}

// Removes all low-opacity paths (see PhantomJS issue #364), and adds
// explicit opacities of unity where absent.

function fix_path_opacities()
{
    page.evaluate(function () {
        var paths = document.getElementsByTagName("path");
        for (var i = paths.length - 1; i >= 0; i--) {
            var path = paths[i];
            var strokeOpacity = path.getAttribute('stroke-opacity');
            if (strokeOpacity == null) {
                path.setAttribute('stroke-opacity', '1.0');
            } else if (strokeOpacity < 0.2) {
                path.parentNode.removeChild(path);
            }
        }
    });
}

function check_page(iter)
{
    // If we have exceeded our check limit, exit.

    if (iter >= iteration_limit) {
        console.log('ERROR: doneness check limit reached.');
        phantom.exit();
    }

    if (get_rendering_status() != '') {
        // Check for completion periodically.
        window.setTimeout('check_page(' + ++iter + ')', iterative_delay_ms);
        return;
    } else {
        // Wait one second before rendering the page. This is due to
        // the fact that sometimes, highcharts sets 'hasRendered' before
        // the chart is fully generated (see bug 140859).
        window.setTimeout('render_page()', iterative_delay_ms);
    }
}

function render_page()
{
    console.log('Rendering page to output file ' + output);
    fix_path_opacities();
    page.render(output);

    console.log('Logging out...');

    page.open(logout_url, function (status) {
        if (status != 'success') {
            console.log('ERROR: logout return status was ' + status);
        }
        console.log('Exiting...');
        phantom.exit();
    });
}

console.log('Opening page ' + address);

page.open(address, function (status) {

    if (status != 'success') {
        console.log('ERROR: Page open return status was ' + status);
        phantom.exit();
    }

    window.setTimeout('check_page(0)', initial_delay_ms);
});
