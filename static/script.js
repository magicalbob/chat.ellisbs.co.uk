$("#ask-button").click(function() {
    // Show loading message and disable button
    $("#loading-message").show();
    $("#ask-button").prop("disabled", true);

    $.ajax({
        url: "/ask",
        type: "post",
        data: JSON.stringify({question: $("#question-input").val()}),
        contentType: "application/json",
        success: function(response) {
            if (response.error) {
                $("#answer").html("<p class='error'>" + response.error + "</p>");
            } else {
                $("#answer").html("<p class='answer'>" + response.answer + "</p>");
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

