/**
 * @jest-environment jsdom
 */

const $ = require('jquery');
const showdown = require('showdown');

// Mocking the showdown converter
jest.mock('showdown', () => {
    return {
        Converter: jest.fn(() => ({
            makeHtml: jest.fn((text) => `<p>${text}</p>`),
        })),
    };
});

// Import the script file
require('./script.js');

describe('script.js Tests', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <textarea id="question-input"></textarea>
            <button id="ask-button">Ask</button>
            <div id="loading-message" style="display: none;"></div>
            <div id="answer"></div>
        `;
    });

    test('Initialize App - Add Event Listeners', () => {
        const spyOnClick = jest.spyOn($.fn, 'click');
        const spyOnKeyPress = jest.spyOn($.fn, 'keypress');

        initializeApp();

        expect(spyOnClick).toHaveBeenCalled();
        expect(spyOnKeyPress).toHaveBeenCalled();
    });

    test('Ask Button Click - Show Loading and Disable Button', () => {
        $("#ask-button").click();
        expect($("#loading-message").css('display')).toBe('block');
        expect($("#ask-button").prop('disabled')).toBe(true);
    });

    test('AJAX Success - Update Answer', () => {
        $.ajax = jest.fn().mockImplementation(({ success }) => {
            success({ answer: 'Test Answer' });
        });

        $("#ask-button").click();
        expect($("#answer").html()).toBe('<p>Test Answer</p>');
    });

    test('AJAX Error - Display Error Message', () => {
        $.ajax = jest.fn().mockImplementation(({ error }) => {
            error({}, 'Error', 'Error occurred');
        });

        $("#ask-button").click();
        expect($("#answer").html()).toBe("<p class='error'>Error: Error</p>");
    });
});
