$(=>
  $("#improvement_search").keydown(->
    console.log("testing")
    ###
    t = $(this)
    window.improvements.fetch(
      data:
        project: t.data('project')
        filter: t.val()
    )
    console.log(window.improvements)
    ###
  )

  # We extend the Backbone.Model prototype to build our own
  Improvement = Backbone.Model.extend(

    # We can pass it default values.
    defaults:
      brief: null
      url_key: null
      project: null
      url_html: null
  )

  ImpSearch = Backbone.Collection.extend(
    model: Improvement

    url: window.api_path + 'improvements/'
  )

  window.improvements = new ImpSearch([])

  ###
  ImpView = Backbone.View.extend(
    template: _.template($("#template-improvement").html())
    tagName: "li"
    initialize: ->
      @_ImpView {}
      @bindAll "add"
      @collection.bind "add", @add
    render: ->

      # This is a dictionary object of the attributes of the models.
      # => { name: "Jason", email: "j.smith@gmail.com" }
      dict = @model.toJSON()

      # Pass this object onto the template function.
      # This returns an HTML string.
      html = @template(dict)

      # Append the result to the view's element.
      $(@el).append html
  )
  ###
)
