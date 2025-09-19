export default function initializeApp(showdownLib) {
  let converter = new showdownLib.Converter();

  // Function to initialize the app
  function updateChatHistory() {
    // Your update logic
  }

  $("#ask-button").click(() => {
    $("#loading-message").show();
    $("#ask-button").prop("disabled", true);

    $.ajax({
      url: "/chat/ask",
      type: "post",
      data: JSON.stringify({ question: $("#question-input").val() }),
      contentType: "application/json",
      success: function (response) {
        if (response.error) {
          $("#answer").html("<p class='error'>" + response.error + "</p>");
        } else {
          let html = converter.makeHtml(response.answer);
          $("#answer").html(html);
        }
        $("#loading-message").hide();
        $("#ask-button").prop("disabled", false);
      },
      error: function (jqXHR, textStatus, errorThrown) {
        $("#answer").html("<p class='error'>Error: " + textStatus + "</p>");
        $("#loading-message").hide();
        $("#ask-button").prop("disabled", false);
      },
    });
  });

  // Other logic
  updateChatHistory();
}
