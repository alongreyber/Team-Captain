var unsaved = false;

$(document).ready(function() {
    // This lets us disable buttons if there are unsaved changes in forms
    $(":input").change(function(){ 
	//triggers change in all input fields including text type
	unsaved = true;
	// Anything with id=publish changes to disabled
	$("#publish").attr("disabled", true);
    });
    $("#submit").on('click', function() {
	unsaved = false;
    });

    var easyMDE = new EasyMDE({
	element: $('#editor')[0]
    });
    
});

function unloadPage(){ 
    if(unsaved){
        return "You have unsaved changes on this page. Do you want to leave this page and discard your changes or stay on this page?";
    }
}

window.onbeforeunload = unloadPage;

// Quick script to allow toggling an element
function toggle_active(id) {
   var e = document.getElementById(id);
   e.classList.toggle("is-active");
}
