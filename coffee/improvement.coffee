'use strict'
mainApp = angular.module("mainApp", ['mainServices', 'mainControllers'])
# Avoid collision with Jinja templates
mainApp.config ($interpolateProvider) ->
  $interpolateProvider.startSymbol "{[{"
  $interpolateProvider.endSymbol "}]}"

mainServices = angular.module("mainServices", ["ngResource"])
mainServices.factory("ImpService", ['$resource', ($resource) ->
  $resource window.api_path + "improvement", {},
    update:
      method: "POST"
    query:
      method: "GET"
      isArray: true
])

mainControllers = angular.module("mainControllers", [])
mainControllers.controller('editController', ['$scope', '$timeout', 'ImpService', ($scope, $timeout, ImpService)->
    $scope.init = (id, brief, desc_md, desc) ->
        $scope.id = id
        $scope.brief = brief
        $scope.brief =
          val: unescape(brief)
          editing: false
          saving: false
          prev: ""
        $scope.desc =
          val: unescape(desc)
          md: unescape(desc_md)
          editing: false
          saving: false
          prev: ""

    $scope.revert = (s) ->
        s.val = s.prev
        $scope.toggle(s)

    $scope.save = (s) ->
        s.saving = true
        ImpService.update(
            brief: $scope.brief.val
            description: $scope.desc.val
            render_md: true
            id: $scope.id
        ,(value) -> # Function to be run when function returns
            if value.success
                $scope.desc.md = value.md
                $timeout ->
                    s.saving = false
                    s.editing = false
                , 1000
            else
                if 'message' of value
                    text = "Error communicating with server. #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{value.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
        )

    $scope.toggle = (s) ->
        s.prev = s.val
        s.editing = !s.editing
])

mainControllers.controller('projectImpSearch', ['$scope', '$timeout', 'ImpService', ($scope, $timeout, ImpService)->
    $scope.init = (project, imps) ->
        $scope.project = project
        $scope.imps = JSON.parse(unescape(imps))

    $scope.search = ->
        $scope.saving = true
        ImpService.query(
            filter: $scope.filter
            project: $scope.project
        ,(value) -> # Function to be run when function returns
            if 'success' not of value
                $timeout ->
                    $scope.imps = value
                , 100
            else
                if 'message' of value
                    text = "Error communicating with server. #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{value.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
        )
])