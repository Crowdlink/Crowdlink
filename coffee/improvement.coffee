'use strict'
mainApp = angular.module("mainApp", ['mainServices', 'mainControllers', 'mainFilters', 'ngRoute'])
# Avoid collision with Jinja templates
mainApp.config ($interpolateProvider) ->
  $interpolateProvider.startSymbol "{[{"
  $interpolateProvider.endSymbol "}]}"

mainApp.config ["$routeProvider", ($routeProvider) ->
  $routeProvider.when("/neverhappening",
    templateUrl: "improvement.html"
    controller: "PhoneListCtrl"
  ).otherwise(
    templateUrl: "main.html"
    controller: "remoteController"
  )
]
mainServices = angular.module("mainServices", ["ngResource"])
mainServices.factory("ImpService", ['$resource', ($resource) ->
  $resource window.api_path + "improvement", {},
    update:
      method: "POST"
      timeout: 5000
    query:
      method: "GET"
      timeout: 5000
      isArray: true
])

mainServices.factory("StripeService", ['$resource', ($resource) ->
  $resource window.api_path + "charge", {},
    update:
      method: "POST"
      timeout: 5000
])

mainControllers = angular.module("mainControllers", [])
mainControllers.controller('editController', ['$scope', '$timeout', 'ImpService', ($scope, $timeout, ImpService)->
    $scope.init = (id, brief, desc_md, desc, status, close_reason) ->
        $scope.id = id
        $scope.brief = brief
        # data type edit templates
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
        # toggle type templates
        $scope.status =
          val: status == 'True'
          saving: false
        # toggle type templates
        $scope.close_reason =
          val: close_reason
          saving: false

    $scope.revert = (s) ->
        s.val = s.prev
        $scope.toggle(s)

    $scope.save = (s, callback) ->
        s.saving = true
        ImpService.update(
            brief: $scope.brief.val
            description: $scope.desc.val
            open: $scope.status.send_val
            render_md: true
            id: $scope.id
        ,(value) -> # Function to be run when function returns
            if value.success
                $scope.desc.md = value.md
                $timeout ->
                    if callback
                      callback()
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
                s.saving = false
        )

    $scope.swap_save = (s) ->
      s.send_val = !s.val
      $scope.save(s, ->
        s.val = !s.val
      )

    $scope.toggle = (s) ->
        s.prev = s.val
        s.editing = !s.editing
])

mainControllers.controller('remoteController', ['$scope', '$routeParams', '$location', '$http', '$sce', ($scope, $routeParams, $location, $http, $sce)->
  $scope.init = () ->
    $scope.test = "false"
    loc = $location.path()
    # this catch feels sketchy because it causes infinite loop if it doesn't work.
    # should probably switch at some point XXX
    if loc == "/" or loc == ""
      loc = "/home"

    console.log(loc)
    $http.get(loc).success((data, status, headers, config) ->
      if "application/json" in headers('Content-Type')
        console.log(data)
      else
        $scope.html_out = $sce.trustAsHtml(data)
        $scope.test = "true"
    )

])

mainControllers.controller('loginController', ['$scope', '$routeParams', '$location', '$http', '$sce', ($scope, $routeParams, $location, $http, $sce)->
  $scope.submit = () ->
    debugger
  $scope.test = () ->
    console.log("dsflgjsdfg")
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

    $scope.vote = (imp) ->
      imp.vote_status = !imp.vote_status
      if imp.vote_status
        imp.votes += 1
      else
        imp.votes -= 1

])

mainControllers.controller('chargeController', ['$scope', 'StripeService', ($scope, StripeService)->
    $scope.init = (sk, userid) ->
      window.handler = StripeCheckout.configure
        token: $scope.recv_token
        key: sk
      $scope.amount = 500
      $scope.userid = userid
      $scope.result =
        text: ""
        type: ""
        show: false

    $scope.recv_token = (token, args) ->
      console.log(args)
      StripeService.update(
          token: token
          amount: $scope.amount
          userid: $scope.userid
      ,(value) -> # Function to be run when function returns
          $scope.result =
            text: "You're card has been successfully charged"
            type: "success"
            show: true
      )

    $scope.pay = () ->
      # Open Checkout with further options
      handler.open
        image: window.static_path + "/img/logo_stripe.png"
        name: "Featurelet"
        description: "Credits ($" + $scope.amount/100 + ")"
        amount: $scope.amount
])

mainControllers.controller('transactionsController', ['$scope', 'StripeService', ($scope, StripeService)->
    $scope.init = (transactions) ->
      $scope.transactions = JSON.parse(unescape(transactions))
      for trans in $scope.transactions
        trans.details = false
])

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
