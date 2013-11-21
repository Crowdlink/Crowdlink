mainControllers = angular.module("mainControllers", [])

# RootController ==============================================================
mainControllers.controller('rootController',
  ($scope, $location, $rootScope, UserService)->
    $scope.init = (logged_in, user_id) ->
      $rootScope.logged_in = logged_in
      $rootScope.user = {}
      UserService.query(
        id: user_id
      ,(value) ->
        $rootScope.user = value
      )

    # update the profile url when the username changes
    $rootScope.$watch('user.username', ->
      $scope.profile = '/' + $rootScope.user.username
    )

    $rootScope.location = $location
    $rootScope.strings =
      err_comm: "Error communicating with server."
)
# IssueController ============================================================
mainControllers.controller('issueController',
  ($scope, $timeout, $routeParams, IssueService)->
    $scope.init = () ->
        IssueService.query(
          username: $routeParams.username
          purl_key: $routeParams.purl_key
          url_key: $routeParams.url_key
          join_prof: "page_join"
        ,(value) ->
          $scope.issue = value[0]
          $scope.prev =
            issue: $.extend({}, value[0])
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
        $scope.issue[s] = $scope.prev.issue[s]
        $scope.toggle(s)

    $scope.save = (s, extra_data={}, callback) ->
        $scope.saving[s] = true
        data =
          id: $scope.issue.id
        if s == 'brief'
          data.brief = $scope.issue.brief
        if s == 'desc'
          data.desc = $scope.issue.desc
        if s == 'open'
          data.open = $scope.issue.open

        IssueService.update(
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
      extra_data[s] = !$scope.issue[s]
      $scope.save(s, extra_data, ->
        $scope.issue[s] = !$scope.issue[s]
      )

    $scope.toggle = (s) ->
      $scope.prev.issue[s] = $scope.issue[s]
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

# AccountController ===========================================================
mainControllers.controller('accountController', ($scope, $location, $rootScope, $routeParams, UserService)->
  $scope.init = ->
    if 'subsection' of $routeParams
      $scope.view = $routeParams.subsection
    else
      $scope.view = 'general'

    # update the profile url when the username changes
    $scope.$watch('view', ->
      $location.path("/account/" + $scope.view)
    )
)

# LoginController ============================================================
mainControllers.controller('loginController', ($scope, $rootScope, UserService, $location)->
  $scope.submit = () ->
    $scope.errors = []
    UserService.login(
        username: $scope.username
        password: $scope.password
    ,(value) ->
        if 'success' of value and value.success
          $rootScope.user = value.user
          $rootScope.logged_in = true
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
  ($scope, $timeout, ProjectService, IssueService, $routeParams)->
    $scope.init = () ->
        $scope.filter = ""
        ProjectService.query(
          username: $routeParams.username
          url_key: $routeParams.url_key
          join_prof: 'page_join'
        ,(value) ->
          $scope.project = value[0]
          $scope.search()
        )

    $scope.search = ->
        $scope.saving = true
        IssueService.query(
            filter: $scope.filter
            project: $scope.project.id
        , (value) -> # Function to be run when function returns
            if 'success' not of value
                $timeout ->
                    $scope.issues = value
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

    $scope.vote = (issue) ->
      issue.vote_status = !issue.vote_status
      if issue.vote_status
        issue.votes += 1
      else
        issue.votes -= 1
)

# ChargeController ============================================================
mainControllers.controller('chargeController', ['$scope', 'StripeService', ($scope, StripeService)->
    $scope.init = () ->
      $scope.options = [500, 1000, 2500, 5000]
      $scope.amount = $scope.options[0]
      $scope.result =
        text: ""
        type: ""
        show: false
      window.handler = StripeCheckout.configure
        token: $scope.recv_token
        key: ""

    reload_custom = ->
      if $scope.amount == false
        if $scope.charge_form.$valid and $scope.custom_amount
          $scope.actual_amt = parseInt($scope.custom_amount) * 100
        else
          $scope.actual_amt = false
    $scope.$watch('custom_amount', reload_custom)

    $scope.$watch('amount', ->
      if $scope.amount
        $scope.actual_amt = $scope.amount
      else
        reload_custom()
    )


    $scope.recv_token = (token, args) ->
      console.log(args)
      StripeService.update(
          token: token
          amount: $scope.actual_amt
          userid: $scope.user.id
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
        description: "Credits ($" + $scope.actual_amt/100 + ")"
        amount: $scope.actual_amt
])

# TransactionController =======================================================
mainControllers.controller('transController', ($scope, $rootScope, TransService)->
  $scope.init = () ->
    TransService.query(
      userid: $rootScope.user.id
    ,(value) ->
      $scope.trans = value
      if trans
        for trans in $scope.transactions
          trans.details = false
    )
)

# ProfileController =======================================================
mainControllers.controller('profileController', ($scope, $rootScope, $routeParams, UserService)->
  $scope.init = () ->
    if $routeParams.username == $rootScope.user.username
      $scope.prof_user = $rootScope.user
    else
      UserService.query(
        username: $routeParams.username
      ,(value) ->
        $scope.prof_user = value
      )
)

# SignupController =======================================================
mainControllers.controller('signupController', ($scope, $rootScope, $routeParams, UserService)->
  $scope.init = () ->

  $scope.submit = () ->
    console.log($scope.form.$error.minlength)
    ###
    UserService.reigster(
      username: $scope.username
      password: $scope.paswword
      email: $scope.email
    ,(value) ->
      if 'success' of value and value.success
        $location.path("/")
      else
        if 'message' of value
          $scope.errors = [value.message, ]
        else
          $scope.errors = [$rootScope.strings.err_comm, ]
    )
    ###
)
