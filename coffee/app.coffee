'use strict'
mainApp = angular.module("mainApp", ['mainServices', 'mainControllers', 'mainFilters', 'ngRoute'])
# Avoid collision with Jinja templates
mainApp.config ($interpolateProvider) ->
  $interpolateProvider.startSymbol "{[{"
  $interpolateProvider.endSymbol "}]}"

mainApp.config ["$routeProvider", ($routeProvider) ->
  $routeProvider.when("/login",
    templateUrl: "templates/login.html"
    controller: "loginController"
  ).otherwise(
    templateUrl: "main.html"
    controller: "remoteController"
  )
]

mainFilters = angular.module("mainFilters", [])
mainFilters.filter('searchFilter', ->
  (input, query, option) ->
    input.replace(RegExp('('+ query + ')', 'gi'), '<span class="match">$1</span>')
)
mainFilters.filter('impFilter', ->
  (input, query, option) ->
    if query in input.brief or query in input.description
        return true
    else
        return false
)

mainApp.directive "dynamic", ($compile) ->
  replace: true
  link: (scope, ele, attrs) ->
    scope.$watch attrs.dynamic, (html) ->
      ele.html html
      $compile(ele.contents()) scope

