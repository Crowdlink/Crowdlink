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
mainControllers.controller('editBriefController', ['$scope', '$timeout', 'ImpService', ($scope, $timeout, ImpService)->
    $scope.init = (id, brief) ->
        $scope.id = id
        $scope.saving = false
        $scope.brief = brief
        $scope.editing = false

    $scope.revert = ->
        $scope.brief = $scope.prev_brief
        $scope.toggle()

    $scope.save = ->
        $scope.saving = true
        ImpService.update(
            brief: $scope.brief
            id: $scope.id
        ,(value) -> # Function to be run when function returns
            if value.success
                $timeout ->
                    $scope.saving = false
                    $scope.editing = false
                , 1000
            else
                if 'message' of value
                    text = "Error communicating with server. #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{error.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
        )

    $scope.toggle = ->
        $scope.prev_brief = $scope.brief
        $scope.editing = !$scope.editing
])

mainControllers.controller('editDescController', ['$scope', '$timeout', 'ImpService', ($scope, $timeout, ImpService)->
    $scope.init = (id, desc_md, desc) ->
        $scope.id = id
        $scope.saving = false
        $scope.editing = false
        $scope.desc = unescape(desc)
        $scope.desc_md = unescape(desc_md)

    $scope.revert = ->
        $scope.desc = $scope.prev_desc
        $scope.toggle()

    $scope.save = ->
        $scope.saving = true
        ImpService.update(
            description: $scope.desc
            id: $scope.id
            render_md: true
        ,(value) -> # Function to be run when function returns
            if value.success
                $scope.desc_md = value.md
                $timeout ->
                    $scope.saving = false
                    $scope.editing = false
                , 1000
            else
                if 'message' of value
                    text = "Error communicating with server. #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{error.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
        )

    $scope.toggle = ->
        $scope.prev_desc = $scope.desc
        $scope.editing = !$scope.editing
] )

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
