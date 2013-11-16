mainControllers = angular.module("mainControllers", [])

# RootController ==============================================================
mainControllers.controller('rootController',
  ($scope, $location, $rootScope)->
    $scope.init = (logged_in, curr_username) ->
      $rootScope.logged_in = logged_in
      $rootScope.curr_username = curr_username

    # update the profile url when the username changes
    $rootScope.$watch('curr_username', ->
      $scope.profile = '/u/' + $rootScope.curr_username
    )

    $rootScope.location = $location
    $rootScope.strings =
      err_comm = "Error communicating with server."
)
# Problemcontroller ============================================================
mainControllers.controller('problemController',
  ($scope, $timeout, $routeParams, ProblemService)->
    $scope.init = () ->
        ProblemService.query(
          username: $routeParams.username
          purl_key: $routeParams.purl_key
          url_key: $routeParams.url_key
        ,(value) ->
          $scope.prob = value[0]
          $scope.prev =
            prob: $.extend({}, value[0])
        )
        $scope.editing =
          brief: false
          desc: false
        $scope.saving =
          brief: false
          desc: false
          close_reason: false
          status: false

    $scope.revert = (s) ->
        $scope.prob[s] = $scope.prev.prob[s]
        $scope.toggle(s)

    $scope.save = (s, extra_data={}, callback) ->
        $scope.saving[s] = true
        data =
          id: $scope.prob.id
        if s == 'brief'
          data.brief = $scope.prob.brief
        if s == 'desc'
          data.desc = $scope.prob.desc
        if s == 'open'
          data.open = $scope.prob.open

        ProblemService.update(
          $.extend(data, extra_data)
        ,(value) -> # Function to be run when function returns
            if 'success' of value and value.success
                $timeout ->
                    if callback
                      callback()
                    $scope.saving[s] = false
                    $scope.editing[s] = false
                , 500
            else
                if 'message' of value
                    text = "Error communicating with server. #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{value.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
                $scope.saving[s] = false
                $scope.editing[s] = false
        )

    $scope.swap_save = (s) ->
      s.send_val = !s.val
      extra_data = {}
      extra_data[s] = !$scope.prob[s]
      $scope.save(s, extra_data, ->
        $scope.prob[s] = !$scope.prob[s]
      )

    $scope.toggle = (s) ->
      $scope.prev.prob[s] = $scope.prob[s]
      $scope.editing[s] = !$scope.editing[s]
)

# RemoteController ============================================================
mainControllers.controller('remoteController', ($scope, $rootScope, $routeParams, $location, $http, $sce)->
  $scope.init = () ->
    loc = $location.path()
    # this catch feels sketchy because it causes infinite loop if it doesn't work.
    # should probably switch at some point XXX
    if loc == "/" or loc == ""
      loc = "/home"

    console.log(loc)
    $http.get(loc).success((data, status, headers, config) ->
      if "application/json" == headers('Content-Type')
        if 'access_denied' of data
          $rootScope.logged_in = false
          $rootScope.curr_username = undefined
          $location.path("/login")
          console.log("Logging out!")
      else
        $scope.html_out = data
    )

)

# LoginController ============================================================
mainControllers.controller('loginController', ($scope, $rootScope, UserService, $location)->
  $scope.submit = () ->
    $scope.errors = []
    UserService.update(
        username: $scope.username
        password: $scope.password
    ,(value) ->
        if 'success' of value and value.success
          $rootScope.logged_in = true
          $rootScope.curr_username = $scope.username
          $location.path("/")
        else
          if 'message' of value
            $scope.errors = [value.message, ]
          else
            $scope.errors = [value.message, ]
      )
)

# ProjectController============================================================
mainControllers.controller('projectController',
  ($scope, $timeout, ProjectService, $routeParams)->
    $scope.init = () ->
        $scope.filter = ""
        ProjectService.query(
          username: $routeParams.username
          url_key: $routeParams.url_key
        ,(value) ->
          $scope.project = value[0]
          $scope.search()
        )

    $scope.search = ->
        $scope.saving = true
        ProplemService.query(
            filter: $scope.filter
            project: $scope.project.id
        , (value) -> # Function to be run when function returns
            if 'success' not of value
                $timeout ->
                    $scope.probs = value
                , 100
            else
                if 'message' of value
                    text = " #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{value.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
        )

    $scope.vote = (prob) ->
      prob.vote_status = !prob.vote_status
      if prob.vote_status
        prob.votes += 1
      else
        prob.votes -= 1
)

# ChargeController ============================================================
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

# TransactionController =======================================================
mainControllers.controller('transactionsController', ['$scope', 'StripeService', ($scope, StripeService)->
    $scope.init = (transactions) ->
      $scope.transactions = JSON.parse(unescape(transactions))
      for trans in $scope.transactions
        trans.details = false
])
