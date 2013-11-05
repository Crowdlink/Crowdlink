$(=>
  APP.Collections.ImpCollection = Backbone.Collection.extend(
    model: APP.Models.Improvement
    url: window.api_path + 'improvements'
  )
  APP.Views.TableView = Backbone.View.extend(
    template: _.template($("#template-table").html())

    initialize: (options) ->
      @collection.bind('reset', @add_all, @)
    render: ->
      @$el.html(@template)
      @add_all()
      @
    add_all: ->
      @$el.find('tbody').children().remove()
      _.each(@collection, $.proxy(this, 'add_one'))
    add_one: (note) ->
      view = new APP.Views.RowView(
        imp: note
        )
      @$el.find('tbody').append(view.render().el)
  )
  APP.Views.RowView = Backbone.View.extend(
    model: APP.Models.Improvement
    template: _.template($("#template-row").html())

    render: ->
      @$el.html @template(@imp.toJSON())
      @
  )

  window.improvements = new APP.Collections.ImpCollection([])
  re_render = ->
    view = new APP.Views.TableView(
      collection: window.improvements
    )
    view.render()
    console.log(view.el)
  )
)
