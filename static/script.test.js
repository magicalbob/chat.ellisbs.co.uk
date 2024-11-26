test("Should handle error response from server", () => {
    // Store the click handler when click is called
    let storedHandler;
    jest.spyOn($, 'ajax');
    
    // Mock jQuery to store the click handler
    const mockJQuery = jest.fn((selector) => ({
      click: jest.fn((handler) => {
        if (handler) storedHandler = handler;
      }),
      val: jest.fn(() => "Test question"),
      html: jest.fn(),
      prop: jest.fn(),
      show: jest.fn(),
      hide: jest.fn(),
    }));
    mockJQuery.ajax = $.ajax;
    global.$ = mockJQuery;

    // Initialize app to set up handlers
    initializeApp(showdown);

    // Mock jQuery ajax to call error callback
    $.ajax.mockImplementation((options) => {
      options.error(null, "Server Error", "Internal Server Error");
    });

    // Call the stored click handler
    storedHandler();

    // Verify loading message is shown and button disabled
    expect($('#loading-message').show).toHaveBeenCalled();
    expect($('#ask-button').prop).toHaveBeenCalledWith('disabled', true);

    // Verify error message is displayed
    expect($('#answer').html).toHaveBeenCalledWith(
      "<p class='error'>Error: Server Error</p>"
    );

    // Verify loading state is cleaned up
    expect($('#loading-message').hide).toHaveBeenCalled();
    expect($('#ask-button').prop).toHaveBeenCalledWith('disabled', false);
});
