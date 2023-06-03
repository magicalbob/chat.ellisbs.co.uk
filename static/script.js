document.getElementById('submit-button').addEventListener('click', function() {
    let question = document.getElementById('question-input').value;

    fetch('/ask', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            'question': question
        })
    }).then(response => response.json())
    .then(data => {
        document.getElementById('answer').textContent = data.answer;
    });
});

