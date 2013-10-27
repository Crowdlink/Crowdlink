# These are development values, and will get overriden after deployment processing
STATIC_PATH = '/static/img/'
API_PATH = '/api/'
# These defns will be used all over the code, but because of their syntax will
# be subbed at deploymenet with configurable values
window.api_path = "#{API_PATH}"
window.static_path = "#{STATIC_PATH}"


###
A simple jquery plugin that registers a button to be able to toggle a value via
AJAX calls. Shows a popover to avoid layout confusions and quick integration.
Shows/Hides applicable content or classes for rendering the current state.
###
(($)->
  # Create a class that attaches itself to jquery plugin syntax. Heavily mimics
  # bootstraps js pattern
  PoverAjax = (element, options) ->
    @type = @options = @element = @data = null
    @init "pover_ajax", element, options

  PoverAjax.DEFAULTS =
      url: ''
      # Whether a popover spinner will be created
      spinner: true
      # direction of the popover that is created
      popover_placement: 'right'
      # How long the popover will linger after saving
      popover_fade: 2000
      error_msg: ""
      success_msg: ""
      # Information on what things to switch based on a boolean data value

      # The data key value that things are switched on, also an on off switch for the functionality
      switch_key: null,
      true_class: null,  # Class that will be put on object for true val
      false_class: null, # "    " for false val
      true_div_sel: null,  # same idea as above, but it will hide show a div
      false_div_sel: null,
      # Functions that will get called optionally on success or fail
      success_func: null,
      error_func: null

  PoverAjax::init = (type, element, options) ->
    @element = $(element)
    @data = @element.data('json')
    @options = @getOptions(options)

    # resync the layout based on data, thinning template logic requirements
    @handle_switch()

    # Register a click handler
    @element.click $.proxy(@run, @)

    # Build the popover, but hide it for now
    if @options.spinner
      @element.popover(
        html: true
        content: "<img src='#{window.static_path}spinner_xs.gif' border='0' />"
        placement: @options.popover_placement
        trigger: 'manual'
      )

  PoverAjax::run = () ->
    # Create a popover spinner if settings enabled
    if @options.spinner
      html = "<img src='#{window.static_path}spinner_xs.gif' border='0' />"
      popover = @element.attr("data-content", html).data("bs.popover")
      popover.setContent()
      popover.$tip.addClass popover.options.placement
      @element.popover('show')

    @data[@options.switch_key] = !@data[@options.switch_key]

    tmp = ->
      $.ajax(
        url: "#{window.api_path}" + @options.url
        type: "POST"
        data: JSON.stringify(@data)
        contentType: 'application/json'
        context: @
        dataType: "json"
      ).done( (jsonObj) ->
        if jsonObj.success
          if @options.spinner
            @replace_popover("<i class='fa green fa-check'></i>")
          if @options.success_func
            @options.success_func()
          @handle_switch()
          @element.popover('show')
        else
          @error_handle(jsonObj.disp)
      ).fail( (jqXHR, textStatus) ->
        @error_handle()
      )
    setTimeout($.proxy(tmp, @), 300)

  # Removes the current popover and replaces it with one that will fade out
  # Used to replace the spinner popover with a resultant one
  PoverAjax::replace_popover = (html) ->
    popover = @element.attr("data-content", html).data("bs.popover")
    popover.setContent()
    popover.$tip.addClass popover.options.placement
    # destroy is in a configured amount of time
    setTimeout($.proxy(->
        @element.popover('hide')
      , this)
    , @options.popover_fade)

  PoverAjax::error_handle = (msg) ->
    # Set the toggle value back to what it was before sending
    @data[@options.switch_key] = !@data[@options.switch_key]
    @handle_switch()
    @element.popover('show')
    if @options.spinner
      html = "<i class='fa red fa-times-circle'></i>"
      if msg
        html += "&nbsp;&nbsp;#{msg}"
      @replace_popover(html)
    if @options.error_func
      @options.error_func()


  # Handle all switching of the layout, etc
  PoverAjax::handle_switch = () ->
    # Don't proc if it's disabled
    if not @options.switch_key
      return
    if @data[@options.switch_key]
      @element.find(@options.false_div_sel).hide()
      @element.find(@options.true_div_sel).show()
      @element.removeClass(@options.false_class)
      @element.addClass(@options.true_class)
    else
      @element.find(@options.false_div_sel).show()
      @element.find(@options.true_div_sel).hide()
      @element.addClass(@options.false_class)
      @element.removeClass(@options.true_class)

  PoverAjax::getDefaults = ->
    PoverAjax.DEFAULTS

  PoverAjax::getOptions = (options) ->
    options = $.extend({}, @getDefaults(), @element.data(), options)
    options

  # Register as a jquery plugin
  $.fn.pover_ajax = (option) ->
    @each ->
      t = $(this)
      data = t.data("pover_ajax")
      options = typeof option is "object" and option
      if not data
        t.data("pover_ajax", (data = new PoverAjax(this, options)))
      if typeof option is "string"
        data[option]()

  # Register our class on the jquery plugin
  $.fn.pover_ajax.Constructor = PoverAjax

) jQuery
