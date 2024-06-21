let converter = new showdown.Converter();

// Function to initialize the app
function initializeApp() {
    // Update the chat history initially
    updateChatHistory();

    // Add event listener to the "Ask" button
    $("#ask-button").click(askQuestion);

    // Add event listener to the question input field (textarea)
    $("#question-input").keypress(function(event) {
        if (event.which === 13 && !event.shiftKey) { // Enter key without Shift
            var text = $("#question-input").val();
            $("#question-input").val(text + "\n"); // Insert newline
            event.preventDefault(); // Prevent default Enter behavior
        } else if (event.which === 13 && event.shiftKey) { // Enter key with Shift
            askQuestion(); // Submit the form
            event.preventDefault(); // Prevent default Enter behavior
        }
    });
}

$("#ask-button").click(function() {
    // Show loading message and disable button
    $("#loading-message").show();
    $("#ask-button").prop("disabled", true);

    $.ajax({
        url: "/chat/ask",
        type: "post",
        data: JSON.stringify({question: $("#question-input").val()}),
        contentType: "application/json",
        success: function(response) {
            if (response.error) {
                $("#answer").html("<p class='error'>" + response.error + "</p>");
            } else {
                let html = converter.makeHtml(response.answer); // Use let instead of var
                $("#answer").html(html);
            }
            // Hide loading message and enable button
            $("#loading-message").hide();
            $("#ask-button").prop("disabled", false);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            $("#answer").html("<p class='error'>Error: " + textStatus + "</p>");
            // Hide loading message and enable button
            $("#loading-message").hide();
            $("#ask-button").prop("disabled", false);
        }
    });
});
