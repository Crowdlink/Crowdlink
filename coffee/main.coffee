$(=>
  image_root = '/static/img/'
  api_root = '/api/'

  window.bind_import = (id) ->
    options = {
        success: (data) ->
            if data[0] == "success"
                $("#alert").removeClass()
                $("#alert").addClass "g"
                $("#alert").html data[1]
            else
                $("#alert").removeClass()
                $("#alert").addClass "b"
                $("#alert").html data[1]
        type: 'POST',
        dataType:'json'
    }


  # Simple fix for hash jumps with bootstrap
  shiftWindow = ->
    scrollBy 0, -70
    setTimeout shiftWindow, 100  if location.hash
    window.addEventListener "hashchange", shiftWindow

  # Utility methods
  replace_spinner = (elm, size='xs') ->
    ret = elm.html()
    elm.html("<img src='#{image_root}spinner_#{size}.gif' border='0' />")

    return ret

  # Register all vote buttons
  $("a[data-type='vote']").click(->
    elm = $(this)
    button = replace_spinner(elm)
    holder = elm
    request = $.ajax(
        url: "#{api_root}vote"
        type: "POST"
        data:JSON.stringify(
            proj_id: elm.data("proj-id")
            url_key: elm.data("url-key")
        )
        contentType: 'application/json'
        dataType: "json"
    )

    err = ->
        elm.html('<div class="btn btn-xs btn-danger">Err</div> ')
        setTimeout(->
            elm.html(button)
        , 2000)

    request.done (jsonObj) ->
        if jsonObj.success
            elm.html('')
        else
            if jsonObj.code == 'already_voted'
                elm.html('<div class="btn btn-xs btn-success">Already Voted</div> ')
                setTimeout(->
                    elm.html('')
                , 2000)
            else
                err()

    request.fail (jqXHR, textStatus) ->
        err()
  )

  # Editing an Improvement brief
  save_brief = (t, key, display, revert) ->
    orig = replace_spinner($("#" + key + "_spinner"))
    restore_spinner = ->
      $("#" + key + "_spinner").html(orig)

    tmp = ->
      $.ajax(
        url: "#{api_root}improvement"
        type: "POST"
        data:JSON.stringify(
            proj_id: t.data("proj-id")
            url_key: t.data("url-key")
            brief: t.find("#" + key + "_input").val()
        )
        contentType: 'application/json'
        dataType: "json"
      ).done( (jsonObj) ->
          if jsonObj.success
            display()
          else
            n = noty(text: "Something went wrong with the request")
          restore_spinner()
      ).fail( (jqXHR, textStatus) ->
          n = noty(text: "Something went wrong with the request")
          restore_spinner()
      )

      setTimeout(tmp, 1000)




  # Edit trigger
  $("[data-type='edit-trigger']").each(->
    # Gets the top level for this edit/display switcher
    t = $(this)
    key = t.attr('id')

    # These generic functions handle swapping the form and value blocks
    # as well as updating the values accordingly
    revert = ->
      # Swap without preserving the form input
      t.find("#" + key + "_edit").hide()
      t.find("#" + key + "_display").show()
    display = ->
      # set the display field to the current output value
      input = t.find("#" + key + "_input").val()
      t.find("#" + key + "_output").html(input)
      # Swap
      t.find("#" + key + "_edit").hide()
      t.find("#" + key + "_display").show()
    edit = ->
      # set the edit field to the current display value
      input = t.find("#" + key + "_output").html()
      t.find("#" + key + "_input").val(input)
      # swap
      t.find("#" + key + "_edit").show()
      t.find("#" + key + "_display").hide()

    # Register the actions
    t.find("[data-action]").click(->
      eval($(this).data('action'))
    )
  )
)
