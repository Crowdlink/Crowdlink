(($) ->
  $.noty.themes.defaultTheme =
    name: "defaultTheme"
    helpers:
      borderFix: ->
        if @options.dismissQueue
          selector = @options.layout.container.selector + " " + @options.layout.parent.selector
          switch @options.layout.name
            when "top"
              $(selector).css borderRadius: "0px 0px 0px 0px"
              $(selector).last().css borderRadius: "0px 0px 5px 5px"
            when "topCenter", "topLeft", "topRight", "bottomCenter", "bottomLeft", "bottomRight", "center", "centerLeft", "centerRight", "inline"
              $(selector).css borderRadius: "0px 0px 0px 0px"
              $(selector).first().css
                "border-top-left-radius": "5px"
                "border-top-right-radius": "5px"

              $(selector).last().css
                "border-bottom-left-radius": "5px"
                "border-bottom-right-radius": "5px"

            when "bottom"
              $(selector).css borderRadius: "0px 0px 0px 0px"
              $(selector).first().css borderRadius: "5px 5px 0px 0px"
            else

    modal:
      css:
        position: "fixed"
        width: "100%"
        height: "100%"
        backgroundColor: "#000"
        zIndex: 10000
        opacity: 0.6
        display: "none"
        left: 0
        top: 0

    style: ->
      @$bar.css
        overflow: "hidden"

      @$message.css
        fontSize: "13px"
        lineHeight: "16px"
        textAlign: "center"
        padding: "8px 10px 9px"
        width: "auto"
        position: "relative"

      @$closeButton.css
        position: "absolute"
        top: 4
        right: 4
        width: 10
        height: 10
        display: "none"
        cursor: "pointer"

      @$buttons.css
        padding: 5
        textAlign: "right"
        borderTop: "1px solid #ccc"
        backgroundColor: "#fff"

      @$buttons.find("button").css marginLeft: 5
      @$buttons.find("button:first").css marginLeft: 0
      @$bar.bind
        mouseenter: ->
          $(this).find(".noty_close").stop().fadeTo "normal", 1

        mouseleave: ->
          $(this).find(".noty_close").stop().fadeTo "normal", 0

      switch @options.layout.name
        when "top"
          @$bar.css
            borderRadius: "0px 0px 5px 5px"
            borderBottom: "2px solid #eee"
            borderLeft: "2px solid #eee"
            borderRight: "2px solid #eee"
            boxShadow: "0 2px 4px rgba(0, 0, 0, 0.1)"

        when "topCenter", "center", "bottomCenter", "inline"
          @$bar.css
            borderRadius: "5px"
            border: "1px solid #eee"
            boxShadow: "0 2px 4px rgba(0, 0, 0, 0.1)"

          @$message.css
            fontSize: "13px"
            textAlign: "center"

        when "topLeft", "topRight", "bottomLeft", "bottomRight", "centerLeft", "centerRight"
          @$bar.css
            borderRadius: "5px"
            border: "1px solid #eee"
            boxShadow: "0 2px 4px rgba(0, 0, 0, 0.1)"

          @$message.css
            fontSize: "13px"
            textAlign: "left"

        when "bottom"
          @$bar.css
            borderRadius: "5px 5px 0px 0px"
            borderTop: "2px solid #eee"
            borderLeft: "2px solid #eee"
            borderRight: "2px solid #eee"
            boxShadow: "0 -2px 4px rgba(0, 0, 0, 0.1)"

        else
          @$bar.css
            border: "2px solid #eee"
            boxShadow: "0 2px 4px rgba(0, 0, 0, 0.1)"

      switch @options.type
        when "alert", "notification"
          @$bar.css
            backgroundColor: "#FFF"
            borderColor: "#CCC"
            color: "#444"

        when "warning"
          @$bar.css
            backgroundColor: "#FFEAA8"
            borderColor: "#FFC237"
            color: "#826200"

          @$buttons.css borderTop: "1px solid #FFC237"
        when "error"
          @$bar.css
            backgroundColor: "#f2dede"
            border: "#ECB6BF 1px solid"
            color: "#b94a48"

          @$message.css fontWeight: "bold"
          @$buttons.css borderTop: "1px solid darkred"
        when "information"
          @$bar.css
            backgroundColor: "#57B7E2"
            borderColor: "#0B90C4"
            color: "#FFF"

          @$buttons.css borderTop: "1px solid #0B90C4"
        when "success"
          @$bar.css
            backgroundColor: "lightgreen"
            borderColor: "#50C24E"
            color: "darkgreen"

          @$buttons.css borderTop: "1px solid #50C24E"
        else
          @$bar.css
            backgroundColor: "#FFF"
            borderColor: "#CCC"
            color: "#444"


    callback:
      onShow: ->
        $.noty.themes.defaultTheme.helpers.borderFix.apply this

      onClose: ->
        $.noty.themes.defaultTheme.helpers.borderFix.apply this
) jQuery
