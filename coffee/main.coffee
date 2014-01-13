$(=>
  # Simple fix for hash jumps with bootstrap
  shiftWindow = ->
    scrollBy 0, -70
    setTimeout shiftWindow, 100  if location.hash
  window.addEventListener "hashchange", shiftWindow

  # ------------- Clickable rows for radio button lists
  $(".record-table").click (event) ->
    $(":radio", this).trigger "click"  if event.target.type isnt "radio"
)
