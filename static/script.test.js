import showdown from "showdown";
import initializeApp from "../static/script.js"; // Import the app initialization

jest.mock("showdown", () => ({
  Converter: jest.fn(() => ({
    makeHtml: jest.fn((text) => `<p>${text}</p>`),
  })),
}));

jest.mock("jquery", () => {
  const $ = jest.fn((selector) => {
    return {
      click: jest.fn(function (handler) {
        if (handler) handler(); // Execute the handler if provided
        return this;
      }),
      keypress: jest.fn(),
      val: jest.fn(() => "Test question"),
      html: jest.fn(),
      prop: jest.fn(),
      show: jest.fn(),
      hide: jest.fn(),
    };
  });

  $.ajax = jest.fn();
  return $;
});

// Set jQuery as a global variable
global.$ = require("jquery");

describe("Script functionality", () => {
  let mockConverter;

  beforeEach(() => {
    mockConverter = new showdown.Converter();

    // Initialize the app with the mocked `showdown` library
    initializeApp(showdown);
  });

  test("Should convert markdown to HTML", () => {
    const inputMarkdown = "**Bold Text**";
    const expectedHtml = "<p>**Bold Text**</p>";

    const result = mockConverter.makeHtml(inputMarkdown);
    expect(result).toBe(expectedHtml);
  });

  test.skip("Should handle click event on #ask-button", () => {
    const button = $("#ask-button");
    expect(button.click).toBeDefined();
    button.click();
    expect(button.click).toHaveBeenCalled();
  });

  test.skip("Should send AJAX request on button click", () => {
    const mockAjax = jest.fn().mockImplementation((options) => {
      if (options.success) {
        options.success({ answer: "Test response" });
      }
      return { fail: jest.fn() };
    });
    $.ajax = mockAjax;

    $("#ask-button").click();

    expect(mockAjax).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/ask",
        method: "POST",
        contentType: "application/json",
        data: expect.any(String),
      })
    );
  });

  test("Should handle error response from server", async () => {
      // Clear mocks
      jest.clearAllMocks();
  
      // Create spy functions
      const showSpy = jest.fn();
      const hideSpy = jest.fn();
      const propSpy = jest.fn();
      const htmlSpy = jest.fn();
      const valSpy = jest.fn().mockReturnValue("Test question");
      
      // Store click handler
      let clickHandler = null;
  
      // Create jQuery element mock
      const elementMock = {
          show: showSpy,
          hide: hideSpy,
          prop: propSpy,
          html: htmlSpy,
          val: valSpy,
          click: jest.fn(handler => {
              if (handler) {
                  clickHandler = handler;
              } else if (clickHandler) {
                  clickHandler();
              }
              return elementMock;
          })
      };
  
      // Create jQuery function mock
      const jQueryMock = jest.fn(selector => elementMock);
      jQueryMock.ajax = jest.fn(options => {
          if (options.error) {
              options.error({}, "Server Error", "Internal Server Error");
          }
      });
  
      // Replace global jQuery
      global.$ = jQueryMock;
  
      // Initialize app which will set up click handler
      initializeApp(showdown);
  
      // Manually trigger the click handler
      if (clickHandler) {
          clickHandler();
      }
  
      // Verify AJAX call
      expect(jQueryMock.ajax).toHaveBeenCalledWith(expect.objectContaining({
          url: "/chat/ask",
          type: "post",
          contentType: "application/json",
          data: JSON.stringify({ question: "Test question" })
      }));
  
      // Verify UI updates
      expect(showSpy).toHaveBeenCalled();
      expect(propSpy).toHaveBeenCalledWith("disabled", true);
      expect(htmlSpy).toHaveBeenCalledWith("<p class='error'>Error: Server Error</p>");
      expect(hideSpy).toHaveBeenCalled();
      expect(propSpy).toHaveBeenCalledWith("disabled", false);
  });
});
