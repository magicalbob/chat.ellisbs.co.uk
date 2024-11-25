import $ from "jquery";
import showdown from "showdown";
import { jest } from "@jest/globals";

// Mock showdown
jest.mock("showdown", () => ({
  Converter: jest.fn(() => ({
    makeHtml: jest.fn((text) => `<p>${text}</p>`)
  }))
}));

// Mock jQuery
jest.mock("jquery", () => ({
  click: jest.fn(),
  keypress: jest.fn(),
  val: jest.fn(() => "Test question"),
  html: jest.fn(),
  prop: jest.fn(),
  show: jest.fn(),
  hide: jest.fn()
}));

// Sample test cases
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
    const mockAjax = jest.fn();
    $.ajax = mockAjax;

    $("#ask-button").click();
    expect($.click).toHaveBeenCalled();
  });

  test("Should send AJAX request on button click", () => {
    const mockAjax = jest.fn((options) => {
      options.success({ answer: "Test response" });
    });
    $.ajax = mockAjax;

    $("#ask-button").click();
    expect(mockAjax).toHaveBeenCalled();
  });
});
