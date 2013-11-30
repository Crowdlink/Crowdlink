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

# SolutionController ============================================================
mainControllers.controller('solutionController',
  ($scope, $routeParams, $rootScope, SolutionService, $timeout)->
    $scope.init = () ->
        SolutionService.query(
            id: $routeParams.id
            join_prof: "page_join"
        ,(value) ->
            $timeout ->
                $scope.sol = value
                $scope.prev =
                    sol: $.extend({}, value)
                $timeout ->
                    $rootScope.loading = false
                , 200
            , 500
        )
        $rootScope.loading = true
        $scope.editing =
          title: false
          desc: false
        $scope.saving =
          title: false
          desc: false

    $scope.$watch('sol.title',(val) ->
      if val
        $rootScope.title = "Solution #{$scope.issue.title} for Issues #{$scope.sol.issue.title}"
      else
        $rootScope.title = "Solution"
    )

    $scope.revert = (s) ->
        $scope.sol[s] = $scope.prev.sol[s]
        $scope.toggle(s)

    $scope.save = (s, extra_data={}, callback) ->
        $scope.saving[s] = true
        data =
          id: $scope.sol.id
        if s == 'title'
          data.title = $scope.sol.title
        if s == 'desc'
          data.desc = $scope.sol.desc

        SolutionService.update(
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
      extra_data[s] = !$scope.sol[s]
      $scope.save(s, extra_data, ->
        $scope.sol[s] = !$scope.sol[s]
      )

    $scope.toggle = (s) ->
      $scope.prev.sol[s] = $scope.sol[s]
      $scope.editing[s] = !$scope.editing[s]
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
            solution_join_prof: "page_join"
        ,(value) ->
            $timeout ->
                $scope.issue = value
                $scope.prev =
                    issue: $.extend({}, value)
                $timeout ->
                    $rootScope.loading = false
                , 200
            , 500
        )
        $rootScope.loading = true
        $scope.editing =
          issue:
            title: false
            desc: false
        $scope.saving =
          issue:
            title: false
            desc: false
            close_reason: false
            status: false
            subscribed: false

    $scope.$watch('issue.title',(val) ->
      if val
        $rootScope.title = "Issue '" + $scope.issue.title + "'"
      else
        $rootScope.title = "Issue"
    )

    $scope.revert = (s) ->
        $scope.issue[s] = $scope.prev.issue[s]
        $scope.toggle(s)

    get = (prefix, dotted) ->
      $scope.$eval(prefix + '.' + dotted)
    set = (prefix, dotted, val) ->
      tmp = $scope.$eval(prefix + '.' + dotted + '=' + val)

    $scope.save = (s, extra_data={}, callback) ->
        frag = s.split('.').pop()
        set('saving', s, true)
        data =
          id: $scope.issue.id
        if frag == 'title'
          data.title = $scope.issue.title
        if frag == 'desc'
          data.desc = $scope.issue.desc
        if frag == 'open'
          data.open = $scope.issue.open

        IssueService.update(
          $.extend(data, extra_data)
        ,(value) -> # Function to be run when function returns
            if 'success' of value and value.success
                $timeout ->
                  if callback
                      callback()
                  set('saving', s, false)
                  set('editing', s, false)
                , 400
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
      val = $scope.$eval(s)
      frag = s.split('.').pop()
      extra_data = {}
      extra_data[frag] = !val
      $scope.save(s, extra_data, ->
        $scope.issue[frag] = !$scope.issue[frag]
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
      join_prof: 'issue_join'
    , (value) -> # Function to be run when function returns
      if 'success' not of value
        $scope.issues = value.issues
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
    ProjectService.query(
        username: $routeParams.username
        url_key: $routeParams.url_key
        join_prof: 'page_join'
    ,(value) ->
        $timeout ->
            $scope.project = value
            $scope.prev =
                project: $.extend({}, value)
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
mainControllers.controller('newProjController', ($scope, $rootScope, $routeParams, $location, ProjectService)->
  $scope.init = () ->
    $rootScope.title = "New Project"
    $scope.auto_key = true

  $scope.$watch('ptitle', (val) ->
    if $scope.auto_key and val != undefined
      $scope.url_key = $scope.ptitle.replace(/\W/g, '-').toLowerCase()
      $scope.form.url_key.$dirty = true
  )

  $scope.submit = ->
    $scope.error_header = ""
    $scope.errors = []
    ProjectService.create(
      name: $scope.ptitle
      url_key: $scope.url_key
      website: $scope.website
      description: $scope.description
    ,(value) ->
      if 'success' of value and value.success
        $location.path("/" + $rootScope.user.username + "/" + $scope.url_key).replace()
      else
        if 'message' of value
          $scope.error_header = "A server side validation error occured, this should not be a common occurance"
          $scope.errors = [value.message, ]
        else if 'validation_errors' of value
          $scope.errors = []
          $scope.error_header = "A server side validation error occured, this should not be a common occurance"
          for idx of value.validation_errors
            capped = idx.charAt(0).toUpperCase() + idx.slice(1) + ": "
            $scope.errors.push(capped + value.validation_errors[idx])
        else
          $scope.errors = [$rootScope.strings.err_comm, ]
    , (error) ->
      debugger
    )
)

# frontpageController =======================================================
mainControllers.controller('frontpageController', ($scope, $rootScope, $routeParams)->
  $scope.init = () ->
    $rootScope.title = ""
)

# newIssueController =======================================================
mainControllers.controller('newissueController', ($scope, $rootScope, $routeParams, $location, ProjectService, IssueService)->
  $scope.init = () ->
    $rootScope.title = "New Issue"
    ProjectService.query(
      username: $routeParams.username
      url_key: $routeParams.url_key
      join_prof: 'issue_join'
      issue_join_prof: 'brief_join'
    , (value) -> # Function to be run when function returns
      if 'success' not of value
        $scope.issues = value.issues
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
  $scope.submit = ->
    $scope.error_header = ""
    $scope.errors = []
    IssueService.create(
      username: $routeParams.username
      purl_key: $routeParams.url_key
      description: $scope.description
      title: $scope.title
    ,(value) ->
      if 'success' of value and value.success
        $location.path("/" + $routeParams.username + "/" + $routeParams.url_key + "/" + value.url_key).replace()
      else
        if 'message' of value
          $scope.error_header = "A server side validation error occured, this should not be a common occurance"
          $scope.errors = [value.message, ]
        else if 'validation_errors' of value
          $scope.errors = []
          $scope.error_header = "A server side validation error occured, this should not be a common occurance"
          for idx of value.validation_errors
            capped = idx.charAt(0).toUpperCase() + idx.slice(1) + ": "
            $scope.errors.push(capped + value.validation_errors[idx])
        else
          $scope.errors = [$rootScope.strings.err_comm, ]
    , (error) ->
      debugger
    )
)

# newSolutionController =======================================================
mainControllers.controller('newSolutionController', ($scope, $rootScope, $routeParams, $location, IssueService, SolutionService)->
  $scope.init = () ->
    $rootScope.title = "New Issue"
    IssueService.query(
      username: $routeParams.username
      purl_key: $routeParams.purl_key
      url_key: $routeParams.url_key
      solution_join_prof: 'disp_join'
    , (value) ->
      if 'success' not of value
        $scope.sols = value.solutions
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
  $scope.submit = ->
    $scope.error_header = ""
    $scope.errors = []
    SolutionService.create(
      username: $routeParams.username
      purl_key: $routeParams.purl_key
      url_key: $routeParams.url_key
      description: $scope.description
      title: $scope.title
    ,(value) ->
      if 'success' of value and value.success
        $location.path("/s/" + value.id + "/" + value.url_key).replace()
      else
        if 'message' of value
          $scope.error_header = "A server side validation error occured, this should not be a common occurance"
          $scope.errors = [value.message, ]
        else if 'validation_errors' of value
          $scope.errors = []
          $scope.error_header = "A server side validation error occured, this should not be a common occurance"
          for idx of value.validation_errors
            capped = idx.charAt(0).toUpperCase() + idx.slice(1) + ": "
            $scope.errors.push(capped + value.validation_errors[idx])
        else
          $scope.errors = [$rootScope.strings.err_comm, ]
    , (error) ->
      debugger
    )
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
