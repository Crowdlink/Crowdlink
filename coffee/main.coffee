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
    $("#" + id).ajaxForm options


# Simple fix for hash jumps with bootstrap
shiftWindow = ->
  scrollBy 0, -70
setTimeout shiftWindow, 100  if location.hash
window.addEventListener "hashchange", shiftWindow

$("a[data-type='vote']").click(=>
  alert('fun!')
)
