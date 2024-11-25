/**
 * @jest-environment jsdom
 */

import $ from 'jquery';
import 'jest-environment-jsdom';
import showdown from 'showdown';
import { initializeApp } from './script';

// Mocking the showdown converter
jest.mock('showdown', () => {
    return {
        Converter: jest.fn(() => ({
            makeHtml: jest.fn((text) => `<p>${text}</p>`),
        })),
    };
});

// Mocking jQuery
jest.mock('jquery', () => {
    const $ = jest.fn(() => ({
        val: jest.fn().mockReturnThis(),
        click: jest.fn(),
        keypress: jest.fn(),
        html: jest.fn(),
        prop: jest.fn(),
        show: jest.fn(),
        hide: jest.fn(),
    }));
    return $;
});

// Test suite
describe('Script.js functionality', () => {
    it('initializes the app and sets up event listeners', () => {
        // Call initializeApp to ensure listeners are attached
        initializeApp();

        expect($('#ask-button').click).toHaveBeenCalled();
        expect($('#question-input').keypress).toHaveBeenCalled();
    });

    it('uses showdown to convert markdown to HTML', () => {
        const converter = new showdown.Converter();
        const result = converter.makeHtml('Hello, world!');
        expect(result).toBe('<p>Hello, world!</p>');
    });
});
