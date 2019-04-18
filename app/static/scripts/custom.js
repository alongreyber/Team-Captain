var unsaved = false;

$(document).ready(function() {
    $(":input").change(function(){ //triggers change in all input fields including text type
	unsaved = true;
	// Anything with the
	$("#publish").attr("disabled", true);
    });
    $("#submit").on('click', function() {
	unsaved = false;
    })
});
function unloadPage(){ 
    if(unsaved){
        return "You have unsaved changes on this page. Do you want to leave this page and discard your changes or stay on this page?";
    }
}

window.onbeforeunload = unloadPage;
