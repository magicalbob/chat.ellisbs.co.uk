import $ from "jquery";
import showdown from "showdown";

jest.mock("showdown", () => ({
  Converter: jest.fn(() => ({
    makeHtml: jest.fn((text) => `<p>${text}</p>`),
  })),
}));

jest.mock("jquery", () => {
  const click = jest.fn();
  const keypress = jest.fn();
  const val = jest.fn(() => "Test question");
  const html = jest.fn();
  const prop = jest.fn();
  const show = jest.fn();
  const hide = jest.fn();

  return () => ({
    click,
    keypress,
    val,
    html,
    prop,
    show,
    hide,
  });
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
