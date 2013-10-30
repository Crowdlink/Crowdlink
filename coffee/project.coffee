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
  initialize: (models, options) ->
    @query = options.query

  url: ->
    window.api_path + 'improvements/' + @query
)

improvements = new ImpSearch([],
  query: "something"
)
improvements.fetch(
  data:
    project: "5269c81b0976194f01e7e0ef"
)
console.log(improvements)

$("#improvement_search").change(->
  improvements.query = $(this).val()
  imrpvoements.fetch()
)

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
