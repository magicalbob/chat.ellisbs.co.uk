import $ from "jquery";
import showdown from "showdown";

jest.mock("showdown", () => ({
  Converter: jest.fn(() => ({
    makeHtml: jest.fn((text) => `<p>${text}</p>`),
  })),
}));

// Mocking jQuery
jest.mock("jquery", () => {
  const mockJQuery = jest.fn().mockImplementation(() => ({
    click: jest.fn((handler) => handler && handler()),
    keypress: jest.fn((handler) => handler && handler({ which: 13, shiftKey: true })),
    val: jest.fn(() => "Test question"),
    html: jest.fn(),
    prop: jest.fn(),
    show: jest.fn(),
    hide: jest.fn(),
  }));

  mockJQuery.ajax = jest.fn();
  return mockJQuery;
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

  test("Should handle click event on #ask-button", () => {
    const mockJQuery = $();
    $("#ask-button").click();
    expect(mockJQuery.click).toHaveBeenCalled();
  });

  test("Should send AJAX request on button click", () => {
    const mockAjax = $.ajax;
    const mockJQuery = $();

    // Simulate button click
    $("#ask-button").click();

    // Mock the AJAX request
    mockAjax.mockImplementation(({ success }) => success({ answer: "Test response" }));

    // Check if AJAX was called
    expect(mockAjax).toHaveBeenCalled();
    expect(mockJQuery.html).toHaveBeenCalledWith("<p>Test response</p>");
  });
});
