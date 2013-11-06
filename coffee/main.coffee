$(=>
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

  # ------------- Editing an Improvement brief
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

  # ---------------------------------------------

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
  ) # ----------------------------------------



  $("a[data-type='vote']").pover_ajax(
    url: 'vote'
    switch_key: 'vote_status'
    true_class: 'btn-info active'
    false_class: 'btn-info'
    true_div_sel: '.true-div'
    false_div_sel: '.false-div'
  )

  $("[data-type='watch']").pover_ajax(
    switch_key: 'subscribed'
    true_class: 'btn-info active'
    false_class: 'btn-info'
    true_div_sel: '.true-div'
    false_div_sel: '.false-div'
  )

  # ------------- Clickable rows for radio button lists
  $(".record-table").click (event) ->
    $(":radio", this).trigger "click"  if event.target.type isnt "radio"
)
