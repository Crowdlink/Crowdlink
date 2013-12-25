mainControllers = angular.module("mainControllers", [])

# parentFormController ========================================================
parentFormController = ($scope) ->
  $scope.error_report = (value) ->
    if 'validation_errors' of value
      $scope.errors = []
      $scope.error_header =
        "A server side validation error occured, this should not occur."
      for idx of value.validation_errors
        capped = idx.charAt(0).toUpperCase() + idx.slice(1) + ": "
        $scope.errors.push(capped + value.validation_errors[idx])
    else if 'message' of value
      $scope.errors = [value.message, ]

    if 'status' of value
      if value.status == 0
        $scope.errors = ["Unable to communicate with server", ]
      else if value.status == 500
        $scope.errors = ["Internal server error, apparently our sites having some troubles...", ]
      else if value.status == 403
        $scope.errors = ["Permission denied. Likely we've made a mistake and let you try to do something you shouldn't be able to try.", ]
      else if value.status == 404
        $scope.errors = ["URL not found, client side sofware error.", ]
      else if value.status == 400
        $scope.errors = ["Client side syntax error, this is a mistake on our part. Sorry about this..", ]
      else
        $scope.errors = ["Unkown error communicating with server", ]

# parentEditController ========================================================
parentEditController = ($scope, $rootScope, $timeout, IssueService,
ProjectService, SolutionService) ->

  $scope.toggle = (s) ->
    $scope.$eval("prev.#{s} = #{s}; editing.#{s} = !editing.#{s}")

  $scope.swap_save = (s) ->
    val = $scope.$eval(s)  # pull out the value
    frag = s.split('.').pop()  # get the attribute name
    extra_data = {}
    extra_data[frag] = !val  # build a data dictionary for save
    $scope.save(s, extra_data, ->
      # only swap the value after save complete
      $scope.$eval("#{s} = !#{s}")
    )

  $scope.save = (s, extra_data={}, callback) ->
    object = s.split('.')
    frag = object.pop()  # get the attribute being saved on the object
    object = $scope.$eval(object.join('.'))  # get the actual object
    set('saving', s, true)

    # abstract out constructing the payload to the controller level
    data = $scope.build_data(frag)

    # determine the service to use to save
    cls = object._cls
    if cls == 'Issue'
      service = IssueService
    else if cls == 'Project'
      service = ProjectService
    else if cls == 'Solution'
      service = SolutionService

    service.update(
      $.extend(data, extra_data)
    ,(value, headers) -> # Function to be run when function returns
      if 'success' of value and value.success
        $timeout ->
          if callback
            callback()
          set('saving', s, false)
          set('editing', s, false)
        , 400
      else
        $rootScope.noty_error(response)
        set('saving', s, false)
        set('editing', s, false)
    , (response) ->
      set('saving', s, false)
      set('editing', s, false)
      $rootScope.noty_error(response)
    )

  get = (prefix, dotted) ->
    $scope.$eval(prefix + '.' + dotted)

  set = (prefix, dotted, val) ->
    tmp = $scope.$eval(prefix + '.' + dotted + '=' + val)

  $scope.revert = (s) ->
    $scope.$eval("#{s} = prev.#{s}")
    $scope.toggle(s)


# RootController ==============================================================
mainControllers.controller('rootController',
($scope, $location, $rootScope, $http, UserService)->

  $scope.init = (logged_in, user) ->
    $rootScope.logged_in = logged_in
    $rootScope.user = {}
    $rootScope.title = ""
    if logged_in
        $rootScope.user = JSON.parse(decodeURIComponent(user))

  $rootScope.noty_error = (response) ->
    options =
      animation:
        open:
          height: 'toggle'
        close:
          height: 'toggle'
        easing: 'swing'
        speed: 200
      layout: "topCenter"
      type: 'error'
      timeout: 4000
    if 'status' of response
      st = response.status
      if st == 400
        noty $.extend(options,
          text: "Unexpected 400 from the server."
        )
      else if st == 403
        noty $.extend(options,
          text: "Unexpected 403 from the server."
        )
      else if st == 404
        noty $.extend(options,
          text: "Unexpected 404 from the server, object may have been deleted."
        )
      else if st == 0
        noty $.extend(options,
          text: "Could not connect to server. Check your internet connection."
        )
    else
      if 'message' of response
        noty $.extend(options,
          text: response.message
        )
      else
        noty $.extend(options,
          text: "An unknown server side error occured"
        )

  $scope.logout = ->
    $http(
      method: 'GET'
      url: '{{ api_path }}logout'
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

  $rootScope.$on('$locationChangeStart', (event, next, current) ->
  )
  $rootScope.$on('$routeChangeError', (event, current, previous, rejection) ->
    curr_path = $location.path()
    if rejection == "login"
      $location.path("/login").search("redirect=" + curr_path).replace()
    if rejection == "not_login"
      $location.path("/home").replace()
  )
)

# SolutionController ==========================================================
mainControllers.controller('solutionController',
  ($scope, $routeParams, $rootScope, $injector, SolutionService, $timeout)->

    $injector.invoke(parentEditController, this, {$scope: $scope})
    $scope.init = () ->
      SolutionService.query(
        __filter_by:
          url_key: $routeParams.url_key
          issue_url_key: $routeParams.iurl_key
          project_url_key: $routeParams.purl_key
          project_maintainer_username: $routeParams.username
        __one: true
        join_prof: "page_join"
      ,(value) ->
        $timeout ->
          $scope.sol = value.objects[0]
          $scope.prev =
            sol: $.extend({}, value.objects[0])
          $timeout ->
            $rootScope.loading = false
          , 200
        , 500
      , $rootScope.noty_error)
      $rootScope.loading = true
      $scope.editing =
        sol:
          title: false
          desc: false
      $scope.saving =
        sol:
          title: false
          desc: false

    $scope.build_data = (frag) ->
      data =
        id: $scope.sol.id
      if frag == 'title'
        data.title = $scope.sol.title
      if frag == 'desc'
        data.desc = $scope.sol.desc

      return data

    $scope.$watch('sol.title', (val) ->
      if val
        $rootScope.title =
          "Solution #{$scope.sol.title} for Issues #{$scope.sol.issue.title}"
      else
        $rootScope.title = "Solution"
    )

)

# IssueController =============================================================
mainControllers.controller('issueController',
($scope, $routeParams, $rootScope, IssueService, $injector, $timeout)->

  $injector.invoke(parentEditController, this, {$scope: $scope})
  $scope.init = () ->
    IssueService.query(
      __filter_by:
        project_maintainer_username: $routeParams.username
        project_url_key: $routeParams.purl_key
        url_key: $routeParams.url_key
      join_prof: "page_join"
    ,(value) ->
      $timeout ->
        $scope.issue = value.objects[0]
        $scope.prev =
          issue: $.extend({}, value.objects[0])
        $timeout ->
          $rootScope.loading = false
        , 200
      , 500
    , $rootScope.noty_error)
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

  $scope.build_data = (frag) ->
    data =
      id: $scope.issue.id
    if frag == 'title'
      data.title = $scope.issue.title
    if frag == 'desc'
      data.desc = $scope.issue.desc
    if frag == 'open'
      data.open = $scope.issue.open

    return data
)

# AccountController ===========================================================
mainControllers.controller('accountController',
($scope, $location, $rootScope, $routeParams, UserService)->
  $scope.init = ->
    $rootScope.title = "Account"
    if 'subsection' of $routeParams
      $scope.view = $routeParams.subsection
    else
      $scope.view = 'general'
)

# ProjectController============================================================
mainControllers.controller('projectController',
($scope, $rootScope, ProjectService, $injector, $routeParams, $timeout)->

  $injector.invoke(parentEditController, this, {$scope: $scope})
  ProjectService.query(
    __filter_by:
      maintainer_username: $routeParams.username
      url_key: $routeParams.url_key
    join_prof: 'page_join'
  , (value, headers) -> # Function to be run when function returns
    if 'success' of value and value.success
      $scope.project = value.objects[0]
      $scope.prev =
        project: $.extend({}, value.objects[0])
      $timeout ->
        $rootScope.loading = false
      , 200
    else
      $rootScope.noty_error value
  , $rootScope.noty_error)

  $scope.init = () ->
    $rootScope.loading = true
    $scope.filter = ""
    $scope.editing =
      project:
        name: false
    $scope.saving =
      project:
        subscribed: false
        vote_status: false
        name: false

  $scope.vote = (issue) ->
    issue.vote_status = !issue.vote_status
    if issue.vote_status
      issue.votes += 1
    else
      issue.votes -= 1

  $scope.build_data = (frag) ->
    data =
      id: $scope.project.id
    if frag == 'name'
      data.name = $scope.project.name

    return data

  # Page title logic. watch the name of the project
  $scope.$watch('project.name',(val) ->
    if val
      $rootScope.title = "Project '" + val + "'"
    else
      $rootScope.title = "Project"
  )
)

# NewChargeController ============================================================
mainControllers.controller('newChargeController',
['$scope', 'StripeService', ($scope, StripeService)->

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
      , $rootScope.noty_error)

    $scope.pay = () ->
      # Open Checkout with further options
      handler.open
        image: "{{ static_path }}img/logo_stripe.png"
        name: "Featurelet"
        description: "Credits ($" + $scope.actual_amt/100 + ")"
        amount: $scope.actual_amt
])

# ChargeController =======================================================
mainControllers.controller('chargeController',
($scope, $rootScope, ChargeService)->

  $scope.init = () ->
    ChargeService.query({}, (value) ->
      $scope.charges = value.charges
      if $scope.charges
        for charge in $scope.charges
          charge.details = false
    , $rootScope.noty_error)
)

# ProfileController ===========================================================
mainControllers.controller('profileController',
($scope, $rootScope, $routeParams, UserService)->

  $scope.init = () ->
    if $routeParams.username == $rootScope.user.username
      $scope.prof_user = $rootScope.user
    else
      UserService.query(
        username: $routeParams.username
      ,(value) ->
        $scope.prof_user = value
      , $rootScope.noty_error)
)

# LoginController =============================================================
mainControllers.controller('loginController',
($scope, $rootScope, $injector, $routeParams, UserService, $location)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
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
        if 'redirect' of $routeParams
          $location.path($routeParams.redirect)
        else
          $location.path("/home")
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# SignupController ============================================================
mainControllers.controller('signupController',
($scope, $rootScope, $routeParams, $injector, UserService)->
  $injector.invoke(parentFormController, this, {$scope: $scope})
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
        $scope.error_report(value)
    , $scope.error_report)
)

# NewProjController ===========================================================
mainControllers.controller('newProjController',
($scope, $rootScope, $routeParams, $location, $injector, ProjectService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
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
      desc: $scope.description
    ,(value) ->
      if 'success' of value and value.success
        $location.path("/" + $rootScope.user.username +
                       "/" + $scope.url_key).replace()
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# newIssueController ==========================================================
mainControllers.controller('newIssueController',
($scope, $rootScope, $routeParams, $location, $injector, ProjectService,
IssueService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.init = () ->
    $rootScope.title = "New Issue"
    IssueService.query(
      __filter_by:
        project_maintainer_username: $routeParams.username
        project_url_key: $routeParams.url_key
      join_prof: 'brief_join'
    , (value) -> # Function to be run when function returns
      if 'success' of value and value.success
        $scope.issues = value.objects
      else
        $rootScope.noty_error value
    , $rootScope.noty_error)
  $scope.submit = ->
    $scope.error_header = ""
    $scope.errors = []
    IssueService.create(
      project_url_key: $routeParams.url_key
      project_maintainer_username: $routeParams.username
      desc: $scope.description
      title: $scope.title
    ,(value) ->
      if 'success' of value and value.success
        issue = value.objects[0]
        $location.path(issue.get_abs_url)
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# newSolutionController =======================================================
mainControllers.controller('newSolutionController',
($scope, $rootScope, $routeParams, $location, $injector, IssueService,
SolutionService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.init = () ->
    $rootScope.title = "New Issue"
    SolutionService.query(
      __filter_by:
          project_maintainer_username: $routeParams.username
          project_url_key: $routeParams.purl_key
          issue_url_key: $routeParams.url_key
      join_prof: 'disp_join'
    , (value) ->
      if 'success' of value and value.success
        $scope.sols = value.objects
      else
        if 'message' of value
          text = " #{value.message}"
        else
          $rootScope.noty_error value
    , $rootScope.noty_error)

  $scope.submit = ->
    $scope.error_header = ""
    $scope.errors = []
    SolutionService.create(
      project_maintainer_username: $routeParams.username
      project_url_key: $routeParams.purl_key
      issue_url_key: $routeParams.url_key
      desc: $scope.desc
      title: $scope.title
    ,(value) ->
      if 'success' of value and value.success
        sol = value.objects[0]
        $location.path(sol.get_abs_url)
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# projectSettingsController ====================================================
mainControllers.controller('projectSettingsController',
($scope, $rootScope, $routeParams, ProjectService)->

  $scope.init = () ->
    $rootScope.title = "Project Settings"
    ProjectService.query(
      __filter_by:
        maintainer_username: $routeParams.username
        url_key: $routeParams.url_key
      __one: true
      join_prof: 'page_join'
    ,(value) ->
      if 'success' of value and value.success
        $scope.project = value.objects[0]
      else
        $rootScope.noty_error value
    , $rootScope.noty_error)
)

# homeController =======================================================
mainControllers.controller('homeController',
($scope, $rootScope, $routeParams, UserService)->

  $scope.init = () ->
    $rootScope.title = "Home"
    UserService.query(
      id: $rootScope.user.id
      join_prof: "home_join"
    ,(value) ->
      $scope.huser = value.objects[0]
    , $rootScope.noty_error)
)

# frontpageController =======================================================
mainControllers.controller('frontpageController',
($scope, $rootScope, $routeParams)->

  $scope.init = () ->
    $rootScope.title = ""
)

# errorController =======================================================
mainControllers.controller('errorController', ($scope, $rootScope, $location)->

  $scope.init = () ->
    $rootScope.title = ""
    err = $location.path().replace('/', '')
    if err == "403"
      $scope.vals =
        txt: "Access Denied"
        long: "You do not have the proper permissions to access the resource" +
              "you requested. This could be an error on our part and if so, " +
              "sorry about that."
        err: "403"
    else if err == "404"
      $scope.vals =
        txt: "Resource not found"
        long: "The resource that you attempted to access could not be found" +
              ". This could be an error on our part and if so, sorry about " +
              "that."
        err: "404"
    else
      $scope.vals =
        txt: "Internal Server Error"
        long: "Our apologies, we seem to have goofed. This error has been " +
              "logged on the server side."
        err: "500"
)
