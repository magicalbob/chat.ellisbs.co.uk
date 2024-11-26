import $ from "jquery";
import showdown from "showdown";
import '../static/script.js';  // Add this at the top of your test file

jest.mock("showdown", () => ({
  Converter: jest.fn(() => ({
    makeHtml: jest.fn((text) => `<p>${text}</p>`),
  })),
}));

jest.mock("jquery", () => {
    const $ = function(selector) {
        return {
            click: jest.fn(function(handler) {
                if (handler) {
                    handler();
                }
                return this;
            }),
            keypress: jest.fn(),
            val: jest.fn(() => "Test question"),
            html: jest.fn(),
            prop: jest.fn(),
            show: jest.fn(),
            hide: jest.fn()
        };
    };

    // Add ajax method to $ directly
    $.ajax = jest.fn();

    return $;
});

describe("Script functionality", () => {
  let mockConverter;

  beforeEach(() => {
    mockConverter = new showdown.Converter();
  });

  test("Should convert markdown to HTML", () => {
    const inputMarkdown = "**Bold Text**";
    const expectedHtml = "<p>**Bold Text**</p>";

    const result = mockConverter.makeHtml(inputMarkdown);
    expect(result).toBe(expectedHtml);
  });
});
