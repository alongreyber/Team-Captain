var unsaved = false;

// Executed every time a form input changes
var changeFunc = function(){ 
    unsaved = true;
    // Anything with id=publish changes to disabled
    $("#publish").attr("disabled", true);
};

// Displays a warning that there are unsaved changes
// Doesn't actually display this text on some browsers (including Chrome)
function displayUnsaved(){ 
    if(unsaved){
        return "You have unsaved changes on this page. Do you want to leave this page and discard your changes or stay on this page?";
    }
}

// Bind displayUnsaved to when we're navigating away from the page
window.onbeforeunload = displayUnsaved;


$(document).ready(function() {
    // Bind to input type
    $(":input").change(changeFunc);

    // Exception to displaying warning is when we click on form submission button
    $("#submit").on('click', function() {
	unsaved = false;
    });

    // Init our editor EasyMDE
    if( $("#editor").length ) {
	var easyMDE = new EasyMDE({
	    element: $('#editor')[0]
	});
	// Bind change function to changes in textarea
	easyMDE.codemirror.on('change', changeFunc);
    }
    
});


// Quick script to allow toggling an element
// Used for notification dropdown
function toggle_active(id) {
   var e = document.getElementById(id);
   e.classList.toggle("is-active");
}

// Send user timezone to server
// timezone_url is set in the base template
var tz = Intl.DateTimeFormat().resolvedOptions().timeZone
$.ajax({
    type: 'POST',
    url: '/submittimezone',
    data: JSON.stringify(tz),
    dataType: 'json',
    contentType: 'application/json; charset=utf-8'
}).done(function(msg) {
    alert("Data Saved: " + msg);
});

$(document).ready(function() {
    if( typeof datePickerSelector !== 'undefined' && $(datePickerSelector).length ) {
	var dueDate = new Date($(maxDateSelector)[0].value);
	var datepicker = $(datePickerSelector).datepicker({
	    language: "en",
	    position: "right top",
	    inline: true,
	    multipleDates: true,
	    multipleDatesSeparator: ", ",
	    minDate: new Date(), // Today
	    maxDate: dueDate
	}).data('datepicker');
	// Select the dates that were previously selected
	const selectedDates = selectedDateStrings.map(st => new Date(st));
	datepicker.selectDate(selectedDates);
	// When the due date changes, reload this widget with correct
	// date constraints
	$(maxDateSelector).change(function() {
	    var dueDate = new Date($(maxDateSelector)[0].value);
	    datepicker.update({ maxDate: dueDate });
	    datepicker.clear();
	});
    }
});
