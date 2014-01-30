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
        $scope.errors = ["Client side syntax error, this likely is a mistake on our part. Sorry about this..", ]
      else if value.status == 409
        $scope.errors = ["One of the submitted data values is a duplicate, and thus submission of this data isn't allowed.", ]
      else if value.status == 402
        $scope.errors = ["The server was unable to execute your requested action.", ]
      else
        $scope.errors = ["Unkown error interacting with server", ]

# parentEditController ========================================================
parentEditController = ($scope, $rootScope, $timeout, TaskService,
ProjectService, UserService) ->

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
    if cls == 'Task'
      service = TaskService
    else if cls == 'Project'
      service = ProjectService
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

  $scope.root_init = (logged_in, user, flashes) ->
    $rootScope.logged_in = logged_in
    $rootScope.title = ""
    if logged_in
      $rootScope.user = JSON.parse(decodeURIComponent(user))
    else
      $rootScope.user = {}
    $rootScope.flash = JSON.parse(decodeURIComponent(flashes))
    $rootScope.messages = {}
    $scope.home = '/'

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

  $scope.payment = (type='pledge') ->
    modalInstance = $modal.open(
      templateUrl: "static/templates/payment_modal.html"
      controller: "paymentModalController"
      resolve:
        payment_type: ->
          type
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
      $rootScope._title = val + " : Crowdlink"
    else
      $rootScope._title = "Crowdlink - Help cool projects grow."
  )

  # update the profile url when the username changes
  $rootScope.$watch('logged_in', (val) ->
    if val
      $scope.profile = '/' + $rootScope.user.username
      $scope.home = '/home'
    else
      $scope.profile = ''
      $scope.home = '/'
  )

  $rootScope.location = $location
  $rootScope.$on('$locationChangeStart', (event, next, current) ->
    $rootScope.loading = true
  )
  $rootScope.$on('$locationChangeSuccess', (event, next, current) ->
    $rootScope.loading = false
    # activate pending flashes
    for message in $rootScope.flash
      id = Date.now() + Math.floor(Math.random() * 100)
      $rootScope.messages[id] = $.extend(
        timeout: 5000
        page_stay: 1
        pages: 0
        messages: []
      , message)
      if $rootScope.messages[id].timeout
        remove = (id) ->
          ->
            delete $rootScope.messages[id]
        $timeout remove(id), $rootScope.messages[id].timeout
    $rootScope.flash = []
    for id, message of $rootScope.messages
      message.pages += 1
      if message.pages > message.page_stay
        delete $rootScope.messages[id]
  )
  $rootScope.$on('$routeChangeError', (event, current, previous, rejection) ->
    $rootScope.loading = false
    if typeof rejection != "string" and 'status' of rejection
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

# TaskController =============================================================
mainControllers.controller('taskController',
($scope, $routeParams, $rootScope, task, $injector, $timeout, CommentService, $location, $anchorScroll) ->

  $scope.toggle_comments = (s) ->
    $scope.$eval("view_comments.#{s} = !view_comments.#{s}")

  $scope.scrollTo = (id) ->
    old = $location.hash()
    $location.hash id
    $anchorScroll()

    #reset to old to keep any additional routing logic from kicking in
    $location.hash old

  $injector.invoke(parentEditController, this, {$scope: $scope})
  $scope.task = task.objects[0]
  $scope.prev =
    task: $.extend({}, task.objects[0])
  $scope.editing =
    task:
      title: false
      desc: false

  $scope.saving =
    task:
      title: false
      desc: false
      status: false
      vote_status: false
      subscribed: false
      report_status: false

  $scope.$watch('task.title',(val) ->
    if val
      $rootScope.title = "Task '" + $scope.task.title + "'"
    else
      $rootScope.title = "Task"
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
      id: $scope.task.id
    if frag == 'title'
      data.title = $scope.task.title
    if frag == 'desc'
      data.desc = $scope.task.desc
    if frag == 'open'
      data.open = $scope.task.open

    return data
)

# AccountController ===========================================================
mainControllers.controller('accountController',
($scope, $location, $modal, $rootScope, $routeParams, $injector, acc_user)->
  $injector.invoke(parentEditController, this, {$scope: $scope})

  $scope.acc_user = acc_user.objects[0]  # pass user info with more information to view
  $scope.saving =
    acc_user:
      gh_linked: false
      tw_linked: false
      go_linked: false
  $scope.init = ->
    $rootScope.title = "Account"
    if 'subsection' of $routeParams
      $scope.view = $routeParams.subsection
    else
      $scope.view = 'general'

  $scope.build_data = (frag) ->
    data =
      id: $scope.acc_user.id
    return data

  $scope.unlink = (provider) ->
    $modal.open(
      templateUrl: "{{template_path}}confirm_modal.html"
      controller: ($scope) ->
        $scope.title = "Are you sure you want to unlink this account?"
    ).result.then ->
      $scope.update(provider, false)
)

# ProjectController============================================================
mainControllers.controller('projectController',
($scope, $rootScope, project, $injector, $routeParams, $timeout, ProjectService)->
  $injector.invoke(parentEditController, this, {$scope: $scope})
  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.project = project.objects[0]
  $rootScope.title = "Project '#{$scope.project.name}'"
  if 'subsection' of $routeParams
    $scope.view = $routeParams.subsection
  else
    $scope.view = 'recent'
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

  $scope.vote = (task) ->
    task.vote_status = !task.vote_status
    if task.vote_status
      task.votes += 1
    else
      task.votes -= 1

  $scope.build_data = (frag) ->
    data =
      id: $scope.project.id
    if frag == 'name'
      data.name = $scope.project.name
    return data

  $scope.new_maintainer = ->
    $scope.remove_maintainer_error = null
    $scope.error_header = ""
    $scope.errors = []
    ProjectService.action(
      username: $scope.username
      id: $scope.project.id
      __action: 'add_maintainer'
    ,(value) ->
      if 'success' of value and value.success
        $scope.project.maintainers.push value.objects[0]
        $scope.f.$setPristine
      else
        $scope.error_report(value)
    , $scope.error_report)

  $scope.remove_maintainer = (idx, username) ->
    $scope.remove_maintainer_error = null
    $scope.error_header = ""
    $scope.errors = []
    ProjectService.action(
      username: username
      id: $scope.project.id
      __action: 'remove_maintainer'
    ,(value) ->
      if 'success' of value and value.success
        $scope.project.maintainers.splice(idx, 1);
      else
        $scope.remove_maintainer_error = idx
    , () ->
      $scope.remove_maintainer_error = null)
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
          $#{$scope.actual_amt/100}. You can now contibute to other projects."
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
  $scope.view = 'feed'
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
    UserService.action(
      identifier: $scope.identifier
      password: $scope.password
      __action: 'login'
      __cls: true
    ,(value) ->
      if 'success' of value and value.success
        $rootScope.user = value.objects[0]
        $rootScope.logged_in = true
        if 'redirect' of $routeParams
          $location.path($routeParams.redirect)
        else
          $location.path("/home")
      else
        $scope.error_report({'message': 'Invalid credentials'})
    , $scope.error_report)
)

# oauthSignupController ============================================================
mainControllers.controller('oauthSignupController',
($scope, $rootScope, $routeParams, $injector, providerData, $location, UserService)->
  $injector.invoke(parentFormController, this, {$scope: $scope})
  $rootScope.title = "Sign Up"
  if 'success' of providerData and providerData.success
    $scope.providerData = providerData.data
    for mail in providerData.data.emails
      if mail.verified
        $scope.primary = mail.email

    if providerData.data.emails.length == 0
      $scope.emailRequired = true
    else
      $scope.optionalPlaceholder = "(Optional)"
      $scope.emailRequired = false
    $scope.load_username = () ->
      $scope.username = providerData.data.username
      # force username check on the server
      $scope.f.username.$dirty = true
      $scope.f.username.$pristine = false
  else
    if 'error' of providerData
      $location.path('/errors/' + providerData.error).replace()
    else
      $location.path('/errors/500').replace()

  prim_update = ->
    if (not $scope.f.email.$valid or not $scope.f.email.$dirty or $scope.email.length == 0) and $scope.primary == "custom"
      $scope.f.primary.$setValidity "valid_email", false
    else
      $scope.f.primary.$setValidity "valid_email", true
  $scope.$watch "primary", prim_update
  $scope.$watch "email", (val) ->
    for mail in providerData.data.emails
      if mail.email == val
        $scope.f.email.$setValidity "duplicate", false
        return
    $scope.f.email.$setValidity "duplicate", true
    # ensure we update the valid status of primary, depends on valid of this
    # field
    prim_update()

  $scope.submit = () ->
    # set primary as the custom email if it was checked
    if $scope.primary == "custom"
      primary = $scope.email
    else
      primary = $scope.primary

    UserService.action(
      username: $scope.username
      password: $scope.pass
      cust_email: $scope.email
      primary: primary
      __action: 'oauth_create'
      __cls: true
    ,(value) ->
      if 'success' of value and value.success
        $rootScope.logged_in = true
        $rootScope.user = value.objects[0]
        $location.path("/home").replace()
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# SignupController ============================================================
mainControllers.controller('signupController',
($scope, $rootScope, $routeParams, $location, $injector, UserService)->
  $injector.invoke(parentFormController, this, {$scope: $scope})
  $rootScope.title = "Sign Up"

  $scope.submit = () ->
    UserService.create(
      username: $scope.username
      password: $scope.pass
      email_address: $scope.email
    , (value) ->
      if 'success' of value and value.success
        $rootScope.logged_in = true
        $rootScope.user = value.objects[0]
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

# newTaskController ==========================================================
mainControllers.controller('newTaskController',
($scope, $rootScope, $routeParams, $location, $injector, tasks, project,
TaskService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $scope.tasks = tasks['objects']
  $scope.project = project['objects'][0]
  $rootScope.title = "New Task"

  $scope.submit = ->
    $scope.error_header = ""
    $scope.errors = []
    TaskService.create(
      project_url_key: $routeParams.url_key
      project_owner_username: $routeParams.username
      desc: $scope.description
      title: $scope.task_title
    ,(value) ->
      if 'success' of value and value.success
        task = value.objects[0]
        $location.path(task.get_abs_url)
      else
        $scope.error_report(value)
    , $scope.error_report)
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

# recoverController =======================================================
mainControllers.controller('recoverController',
($scope, $rootScope, $routeParams, $location, $injector, UserService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $rootScope.title = "Recover Account"
  $scope.submit = ->
    UserService.action(
      password: $scope.pass
      hash: $routeParams.hash
      id: $routeParams.user_id
      __action: 'recover'
    ,(value) ->
      if 'success' of value and value.success
        $rootScope.flash.push(
          message: "Successfully changed your password. You're now logged in."
          timeout: null
          class: 'alert-success'
        )
        $rootScope.user = value.objects[0]
        $rootScope.logged_in = true
        $location.path("/home")
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# sendRecoverController =======================================================
mainControllers.controller('sendRecoverController',
($scope, $rootScope, $routeParams, $location, $injector, UserService)->

  $injector.invoke(parentFormController, this, {$scope: $scope})
  $rootScope.title = "Recover Account"
  $scope.submit = ->
    UserService.action(
      identifier: $scope.identifier
      __action: 'send_recover'
      __cls: true
    ,(value) ->
      if 'success' of value and value.success
        $rootScope.flash.push(
          message: "An email has been sent to #{value.email} with recovery instructions."
          timeout: null
          class: 'alert-success'
        )
        $location.path("/login")
      else
        $scope.error_report(value)
    , $scope.error_report)
)

# errorController =======================================================
mainControllers.controller('errorController', ($scope, $routeParams, $rootScope)->
  $scope.error_data =
    "400":
      subtext: "400"
      txt: "Incorrect Request Format"
      long: "Our apologies, we seem to have goofed. This error is likely a
 mistake in our client side code, hopefully we'll have this fixed soon."
    "500":
      subtext: "500"
      txt: "Internal Server Error"
      long: "Our apologies, we seem to have goofed."
    "404":
      subtext: "404"
      txt: "Resource not found"
      long: "The resource that you attempted to access could not be found.
 This could be an error on our part and if so, sorry about that."
    "403":
      subtext: "403"
      txt: "Access Denied"
      long: "You do not have the proper permissions to access the resource
 you requested. This could be an error on our part and if so, sorry about that."
    "oauth_email_present":
      subtext: "Error"
      txt: "OAuth Email Address Present"
      long: "One of the email addresses returned by the OAuth provider has
 already been registered by a user in our system, thus we cannot create a new
 account linked to this provider. If you've forgotten the password to this
 account you can perform password recovery. If you don't believe you've created
 an account that is using these email addresses please contact support."
    "oauth_already_linked":
      subtext: "Error"
      txt: "OAuth Already Linked"
      long: "Your account is already linked to an account with that OAuth provider."
    "oauth_linked_other":
      subtext: "Error"
      txt: "Account Already Linked"
      long: "Another account is already linked to that account with that OAuth
 provider."
    "oauth_comm_error":
      subtext: "Error"
      txt: "OAuth Communication Failure"
      long: "There was an error interacting with the OAuth provider. This
 happens occasionaly when they fail to respond as expected, so a retry might be
 in order. If problem persists please contact us as it's possibly a bug in our
 system."
    "oauth_error":
      subtext: "Error"
      txt: "OAuth Error"
      long: "An unexpected error has occured with our OAuth system, and has
 been logged. If you are repeatedly encountering this error please conteact us."
  if $routeParams.error not of $scope.error_data
    $scope.err = 500
  else
    $scope.err = $routeParams.error
  $rootScope.title = $scope.error_data[$scope.err]['txt']
)

# helpModalController =======================================================
mainControllers.controller('helpModalController', ($sce, $scope, $modalInstance, $rootScope, $http, topic) ->
  $scope.init = () ->
    $rootScope.loading = true
    $http.get('{{ static_path }}faq.json').success((data) ->
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

# paymentModalController =======================================================
mainControllers.controller('paymentModalController', ($sce, $scope, $modalInstance, $rootScope, $http, payment_type) ->
  $scope.init = () ->
    $rootScope.loading = true
    $http.get('{{ static_path }}payment_ranges.json').success((data) ->
      $scope.ranges = data['ranges']
      $scope.payment_type = payment_type
      $scope.payment_amt = 1.0
      $scope.balance = 8.73
    )
    $rootScope.loading = false
  $scope.close = ->
    $modalInstance.dismiss "close"
  $scope.change_payment_type = (new_payment_type) ->
    $scope.payment_type = new_payment_type
  $scope.change_payment_amt = (new_payment_amt) ->
    $scope.payment_amt = new_payment_amt
)
