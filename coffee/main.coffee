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
