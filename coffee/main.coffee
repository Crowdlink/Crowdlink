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

  replace_spinner = (elm, size='xs') ->
    ret = elm.html()
    elm.html("<img src='#{image_root}spinner_#{size}.gif' border='0' />")

    return ret

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

  $("#improvement-brief-edit").click(edit_brief = ->
    elm = $(this).parent()
    holder = elm.html()
    elm.html("<div class='col-lg-8'><input id='new-value' type='text' value='#{elm.data('current')}' class='form-control' /></div>"+
    "<div class='btn btn-info icon-save' id='improvement-save'></div> "+
    "<div class='btn btn-default icon-remove' id='improvement-cancel'></div>")
    revert = ->
      elm.html(holder)
      elm.find("#brief-text").html(elm.data('current'))
      elm.find("#improvement-brief-edit").click(edit_brief)


    $("div#improvement-cancel").click(->
      revert()
    )

    $("div#improvement-save").click ->
      elm = $(this).parent()
      request = $.ajax(
          url: "#{api_root}improvement"
          type: "POST"
          data:JSON.stringify(
              proj_id: elm.data("proj-id")
              url_key: elm.data("url-key")
              brief: elm.find("#new-value").val()
          )
          contentType: 'application/json'
          dataType: "json"
      )

      request.done (jsonObj) ->
        if jsonObj.success
          elm.data('current', elm.find("#new-value").val())
          revert()
        else
          if jsonObj.code == 'already_voted'
            elm.html('<div class="btn btn-xs btn-success">Already Voted</div> ')
          else
            n = noty(text: "noty - a jquery notification library!")

      request.fail (jqXHR, textStatus) ->
        n = noty(text: "noty - a jquery notification library!")
  )
)
