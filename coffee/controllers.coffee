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
ProjectService, SolutionService, UserService) ->

  $scope.toggle = (s) ->
    $scope.$eval("prev.#{s} = #{s}; editing.#{s} = !editing.#{s}")

  $scope.update = (s, new_val) ->
    val = $scope.$eval(s)  # pull out the value
    frag = s.split('.').pop()  # get the attribute name
    extra_data = {}
    extra_data[frag] = new_val  # build a data dictionary for save
    $scope.save(s, extra_data, ->
      # only change after the value after save completes
      if typeof new_val == "boolean"
        $scope.$eval("#{s} = #{new_val}")
      else
        $scope.$eval("#{s} = '#{new_val}'")
    )

  $scope.swap_save = (s) ->
    $scope.update(s, !$scope.$eval(s))

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
    else if cls == 'User'
      service = UserService

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
($scope, $location, $rootScope, $http, $modal, $timeout, UserService)->

  $scope.root_init = (logged_in, user) ->
    $rootScope.logged_in = logged_in
    $rootScope.title = ""
    if logged_in
      $rootScope.user = JSON.parse(decodeURIComponent(user))
    else
      $rootScope.user = {}
    $rootScope.flash = []

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

  $scope.help = (view='what_is') ->
    modalInstance = $modal.open(
      templateUrl: "static/templates/help_modal.html"
      controller: "helpModalController"
      resolve:
        topic: ->
          view
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
  $rootScope.$on('$locationChangeStart', (event, next, current) ->
    $rootScope.loading = true
  )
  $rootScope.$on('$locationChangeSuccess', (event, next, current) ->
    $rootScope.loading = false
    # Swap our pending flash events to display for two seconds when the route
    # is changed
    if $rootScope.flash.length > 0
      $rootScope.messages = $rootScope.flash.slice 0
      $rootScope.flash = []
      $timeout( ->
        $rootScope.messages = []
      , 2000)
  )
  $rootScope.$on('$routeChangeError', (event, current, previous, rejection) ->
    $rootScope.loading = false
    if 'status' of rejection
      st = rejection.status
      if st == 400
        $location.path("/errors/400").replace()
      else if st == 403
        $location.path("/errors/403").replace()
      else if st == 500
        $location.path("/errors/500").replace()
      else if st == 404
        $location.path("/errors/404").replace()
    curr_path = $location.path()
    if rejection == "login"
      $location.path("/login").search("redirect=" + curr_path).replace()
    if rejection == "not_login"
      $location.path("/home").replace()
  )
)

# SolutionController ==========================================================
mainControllers.controller('solutionController',
  ($scope, $routeParams, $rootScope, $injector, solution, $timeout)->

    $injector.invoke(parentEditController, this, {$scope: $scope})
    $scope.sol = solution.objects[0]
    $scope.prev =
      sol: $.extend({}, solution.objects[0])
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
($scope, $routeParams, $rootScope, issue, $injector, $timeout, CommentService) ->

  $injector.invoke(parentEditController, this, {$scope: $scope})
  $scope.issue = issue.objects[0]
  $scope.prev =
    issue: $.extend({}, issue.objects[0])
  $scope.editing =
    issue:
      title: false
      desc: false
  $scope.saving =
    issue:
      title: false
      desc: false
      status: false
      vote_status: false
      subscribed: false
      report_status: false

  $scope.$watch('issue.title',(val) ->
    if val
      $rootScope.title = "Issue '" + $scope.issue.title + "'"
    else
      $rootScope.title = "Issue"
  )

  $scope.comment = (message, object) ->
    CommentService.create(
      message: message
      thing_id: object.id
    ,(value) ->
      if 'success' of value and value.success
        $timeout ->
          object.comments.push(value.objects[0])
        , 500
      else
        $rootScope.noty_error value
    , $rootScope.noty_error)

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
($scope, $location, $rootScope, $routeParams, acc_user)->
  $scope.acc_user = acc_user.objects[0]  # pass user info with more information to view
  $scope.init = ->
    $rootScope.title = "Account"
    if 'subsection' of $routeParams
      $scope.view = $routeParams.subsection
    else
      $scope.view = 'general'
)

# ProjectController============================================================
mainControllers.controller('projectController',
($scope, $rootScope, project, $injector, $routeParams, $timeout)->

  $injector.invoke(parentEditController, this, {$scope: $scope})
  $scope.project = project.objects[0]
  $rootScope.title = "Project '#{$scope.project.name}'"
  $scope.prev =
    project: $.extend({}, project.objects[0])
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

)

# NewChargeController ============================================================
mainControllers.controller('newChargeController', ($scope, $rootScope,
$injector, ChargeService, $location)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.options = [500, 1000, 2500, 5000]
  $scope.amount = $scope.options[0]
  $scope.result =
    text: ""
    type: ""
    show: false
  $scope.handler = StripeCheckout.configure
    token: (token, args) ->
      $scope.recv_token(token, args)
    key: "{{ stripe_public_key }}"

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
    ChargeService.create(
      token: token
      amount: $scope.actual_amt
    ,(value) -> # Function to be run when function returns
      if 'success' of value and value.success
        $rootScope.flash.push
          message: "Successfully charged your card for
          $#{$scope.actual_amt /100}. You can now contibute to other projects."
          class: 'alert-success'
        $location.path("/account/charges")
      else
        $scope.error_report(value)
    , $scope.error_report)

  $scope.pay = () ->
    # Open Checkout with further options
    $scope.handler.open
      image: "{{ static_path }}img/logo_stripe.png"
      name: "Featurelet"
      description: "Credits ($" + $scope.actual_amt/100 + ")"
      amount: $scope.actual_amt
)

# ChargeController =======================================================
mainControllers.controller('chargeController',
($scope, $rootScope, ChargeService)->
  ChargeService.query(
    __filter_by:
      user_id: $rootScope.user.id
    __order_by: '["created_at"]'
  , (value) ->
    $scope.charges = value.objects
    if $scope.charges
      for charge in $scope.charges
        charge.details = false
  , $rootScope.noty_error)
)

# ProfileController ===========================================================
mainControllers.controller('profileController',
($scope, $rootScope, $routeParams, prof_user, $injector)->
  $injector.invoke(parentEditController, this, {$scope: $scope})
  $scope.prof_user = prof_user.objects[0]
  $scope.build_data = (frag) ->
    data =
      id: $scope.prof_user.id
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
($scope, $rootScope, $routeParams, $location, $injector, issues,
IssueService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.issues = issues
  $rootScope.title = "New Issue"

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
($scope, $rootScope, $routeParams, $location, $injector, solutions, SolutionService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.sols = solutions.objects[0]
  $rootScope.title = "New Issue"

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
($scope, $rootScope, $routeParams, project)->
  $rootScope.title = "Project Settings"
  $rootScope.project = project.objects[0]
)

# homeController =======================================================
mainControllers.controller('homeController',
($scope, $rootScope, $routeParams, huser)->
  $rootScope.title = "Home"
  $scope.huser = huser.objects[0]
)

# frontpageController =======================================================
mainControllers.controller('frontPageController',
($scope, $rootScope, $routeParams)->
  $rootScope.title = ""
)

# errorController =======================================================
mainControllers.controller('errorController', ($scope, $routeParams, $rootScope)->
  $scope.err = $routeParams.error
  $scope.error_data =
    "400":
      txt: "Incorrect Request Format"
      long: "Our apologies, we seem to have goofed. This error is likely a
        mistake in our client side code, hopefully we'll have this
        fixed soon."
    "500":
      txt: "Internal Server Error"
      long: "Our apologies, we seem to have goofed. This error has been
        logged on the server side."
    "404":
      txt: "Resource not found"
      long: "The resource that you attempted to access could not be found.
        This could be an error on our part and if so, sorry about
        that."
    "403":
      txt: "Access Denied"
      long: "You do not have the proper permissions to access the resource
        you requested. This could be an error on our part and if so,
        sorry about that."
  $rootScope.title = $scope.error_data[$scope.err]['txt']
)

# helpModalController =======================================================
mainControllers.controller('helpModalController', ($sce, $scope, $modalInstance, $rootScope, $http, topic) ->
  $scope.init = () ->
    $rootScope.loading = true
    $http.get('assets/help/faq.json').success((data) ->
      $scope.cats = data['categories']
      $scope.topics = data['topics']
      for c_topic, vals of $scope.topics
        $scope.topics[c_topic]['body'] = $sce.trustAsHtml($scope.topics[c_topic]['body'])
      $rootScope.loading = false
      $scope.curr_topic = $scope.topics[topic]
    )
  $scope.close = ->
    $modalInstance.dismiss "close"
  $scope.update = (new_topic) ->
    return $scope.curr_topic = new_topic
)
