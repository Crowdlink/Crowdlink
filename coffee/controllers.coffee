mainControllers = angular.module("mainControllers", [])

# RootController ==============================================================
mainControllers.controller('rootController', ($scope, $location, $rootScope, $http, UserService)->
    $scope.init = (logged_in, user_id) ->
      $rootScope.logged_in = logged_in
      $rootScope.user = {}
      $rootScope.title = ""
      if logged_in
        UserService.query(
          id: user_id
        ,(value) ->
          $rootScope.user = value
        )

    $scope.logout = ->
      $http(
        method: 'GET'
        url: window.api_path + 'logout'
      ).success((data, status, headers) ->
        if data.access_denied
          $rootScope.logged_in = false
          $rootScope.user = {}
          $location.path('/').replace()
        # XXX; Need some error handling here
      ).error((data, status, headers) ->
        # XXX; Need some error handling here
      )


    # update the title with a suffix
    $rootScope.$watch('title', (val) ->
      if val
        $rootScope._title = val + " : Crowd Link"
      else
        $rootScope._title = "Crowd Link"
    )

    # update the profile url when the username changes
    $rootScope.$watch('user.username', (val) ->
      if $rootScope.logged_in
        $scope.profile = '/' + val
      else
        $scope.profile = ""
    )

    $rootScope.location = $location
    $rootScope.strings =
      err_comm: "Error communicating with server."
)
# IssueController ============================================================
mainControllers.controller('issueController',
  ($scope, $routeParams, $rootScope, IssueService, $timeout)->
    $scope.init = () ->
        IssueService.query(
            username: $routeParams.username
            purl_key: $routeParams.purl_key
            url_key: $routeParams.url_key
            join_prof: "page_join"
        ,(value) ->
            $timeout ->
                $scope.issue = value[0]
                $scope.prev =
                    issue: $.extend({}, value[0])
                $timeout ->
                    $rootScope.loading = false
                , 200
            , 500
        )
        $rootScope.loading = true
        $scope.editing =
          brief: false
          desc: false
        $scope.saving =
          brief: false
          desc: false
          close_reason: false
          status: false

    $scope.$watch('issue.brief',(val) ->
      if val
        $rootScope.title = "Issue '" + $scope.issue.brief + "'"
      else
        $rootScope.title = "Issue"
    )

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
                if callback
                    callback()
                $scope.saving[s] = false
                $scope.editing[s] = false
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

# AccountController ===========================================================
mainControllers.controller('accountController', ($scope, $location, $rootScope, $routeParams, UserService)->
  $scope.init = ->
    $rootScope.title = "Account"
    if 'subsection' of $routeParams
      $scope.view = $routeParams.subsection
    else
      $scope.view = 'general'

    # update the profile url when the username changes
    $scope.$watch('view', ->
      $location.path("/account/" + $scope.view).replace()
    )
)

# LoginController ============================================================
mainControllers.controller('loginController', ($scope, $rootScope, UserService, $location)->
  $scope.init = ->
    if $rootScope.logged_in
      $location.path("/home").replace()
    $rootScope.title = "Login"
  $scope.submit = () ->
    $scope.errors = []
    UserService.login(
        username: $scope.username
        password: $scope.password
    ,(value) ->
        if 'success' of value and value.success
          $rootScope.user = value.user
          $rootScope.logged_in = true
          $location.path("/home")
        else
          if 'message' of value
            $scope.errors = [value.message, ]
          else
            $scope.errors = [value.message, ]
      )
)

# ProjectController============================================================
mainControllers.controller('projectController', ($scope, $rootScope, ProjectService, IssueService, $routeParams, $timeout)->
    ProjectService.query(
        username: $routeParams.username
        url_key: $routeParams.url_key
        join_prof: 'page_join'
    ,(value) ->
        $timeout ->
            $scope.project = value
            $scope.prev =
                project: $.extend({}, value)
            $scope.search()
            $timeout ->
                $rootScope.loading = false
            , 200
        , 500
    )
    $scope.init = () ->
      $rootScope.loading = true
      $scope.filter = ""
      $scope.editing =
        name: false
      $scope.saving =
        subscribed: false
        vote_status: false
        name: false

    # Update the list of issues in realtime as they type
    $scope.search = ->
        IssueService.query(
            filter: $scope.filter
            project: $scope.project.id
        , (value) -> # Function to be run when function returns
            if 'success' not of value
                $scope.issues = value
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

    $scope.revert = (s) ->  # For canceling an edit
        $scope.project[s] = $scope.prev.project[s]
        $scope.toggle(s)

    # Saving the project to the database
    $scope.save = (s, extra_data={}, callback) ->
        $scope.saving[s] = true
        data =
          id: $scope.project.id
        if s == 'name'
          data.name = $scope.project.name

        ProjectService.update(
          $.extend(data, extra_data)
        ,(value) -> # Function to be run when function returns
            if 'success' of value and value.success
                if callback
                    callback()
                $scope.saving[s] = false
                $scope.editing[s] = false
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

    # used for changing boolean values and saving in one step
    $scope.swap_save = (s) ->
      extra_data = {}
      extra_data[s] = !$scope.project[s]
      $scope.save(s, extra_data, ->
        $scope.project[s] = !$scope.project[s]
      )

    # switch editing and back
    $scope.toggle = (s) ->
      $scope.prev.project[s] = $scope.project[s]
      $scope.editing[s] = !$scope.editing[s]

    # Page title logic. watch the name of the project
    $scope.$watch('project.name',(val) ->
      if val
        $rootScope.title = "Project '" + val + "'"
      else
        $rootScope.title = "Project"
    )
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
    $rootScope.title = "Sign Up"

  $scope.submit = () ->
    UserService.reigster(
      username: $scope.username
      password: $scope.paswword
      email: $scope.email
    ,(value) ->
      if 'success' of value and value.success
        $location.path("/home").replace()
      else
        if 'message' of value
          $scope.errors = [value.message, ]
        else
          $scope.errors = [$rootScope.strings.err_comm, ]
    )
)

# NewProjController =======================================================
mainControllers.controller('newProjController', ($scope, $rootScope, $routeParams)->
  $scope.init = () ->
    $rootScope.title = "New Project"
    $scope.auto_key = true

  $scope.$watch('ptitle', (val) ->
    if $scope.auto_key and val != undefined
      $scope.url_key = $scope.ptitle.replace(/\W/g, '-').toLowerCase()
  )

)

# frontpageController =======================================================
mainControllers.controller('frontpageController', ($scope, $rootScope, $routeParams)->
  $scope.init = () ->
    $rootScope.title = ""
)

# newIssueController =======================================================
mainControllers.controller('newissueController', ($scope, $rootScope, $routeParams)->
  $scope.init = () ->
    $rootScope.title = "New Issue"
)

# projectSettingsController ====================================================
mainControllers.controller('projectSettingsController', ($scope, $rootScope, $routeParams, ProjectService)->
  $scope.init = () ->
    $rootScope.title = "Project Settings"
    ProjectService.query(
      username: $routeParams.username
      url_key: $routeParams.url_key
      join_prof: 'page_join'
    ,(value) ->
      $scope.project = value[0]
    )
)

# homeController =======================================================
mainControllers.controller('homeController', ($scope, $rootScope, $routeParams, UserService)->
  $scope.init = () ->
    $rootScope.title = "Home"
    UserService.query(
      id: $rootScope.user.id
      join_prof: "home_join"
    ,(value) ->
      $scope.huser = value
    )
)
