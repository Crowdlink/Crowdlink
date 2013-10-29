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
