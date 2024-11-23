/**
 * @jest-environment jsdom
 */
const $ = require("jquery");
const showdown = require("showdown");
require("@testing-library/jquery");

const { initializeApp } = require("../static/script");

describe("script.js", () => {
  beforeEach(() => {
    // Set up DOM
    document.body.innerHTML = `
      <textarea id="question-input"></textarea>
      <button id="ask-button">Ask</button>
      <div id="loading-message" style="display:none;"></div>
      <div id="answer"></div>
    `;

    // Initialize app
    initializeApp();
  });

  test("should initialize the app correctly", () => {
    const askButton = $("#ask-button");
    expect(askButton).toBeDefined();
    expect(typeof askButton.click).toBe("function");
  });

  test("should handle AJAX success response", () => {
    const converter = new showdown.Converter();
    const mockResponse = {
      answer: "This is a **bold** response"
    };

    // Simulate AJAX success
    $.ajax = jest.fn().mockImplementation(({ success }) => {
      success(mockResponse);
    });

    $("#question-input").val("Test question");
    $("#ask-button").click();

    expect($("#answer").html()).toBe(converter.makeHtml(mockResponse.answer));
  });

  test("should handle AJAX error response", () => {
    const mockError = { statusText: "Internal Server Error" };

    // Simulate AJAX error
    $.ajax = jest.fn().mockImplementation(({ error }) => {
      error(mockError);
    });

    $("#question-input").val("Test question");
    $("#ask-button").click();

    expect($("#answer").html()).toBe(
      "<p class='error'>Error: Internal Server Error</p>"
    );
  });
});
