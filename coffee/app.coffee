'use strict'
mainApp = angular.module("mainApp",
  ['mainServices',
   'mainControllers',
   'mainFilters',
   'ngRoute',
   'ngAnimate',
   'ui.bootstrap']
)
# Avoid collision with Jinja templates
mainApp.config ($interpolateProvider) ->
  $interpolateProvider.startSymbol "{[{"
  $interpolateProvider.endSymbol "}]}"

login_resolver = (auth_level) ->
  ($q, $rootScope) ->
    if auth_level == 'user' and not $rootScope.logged_in
      return $q.reject "login"

    if auth_level == 'not_user' and $rootScope.logged_in
      return $q.reject "not_login"

    deferred = $q.defer()
    deferred.resolve()
    deferred.promise

mainApp.config ["$routeProvider", ($routeProvider) ->
  $routeProvider.when("/login",
    templateUrl: "templates/login.html"
    controller: "loginController"
  ).when("/logout",
    templateUrl: "main.html"
    controller: "remoteController"
  ).when("/",
    templateUrl: "templates/home.html"
    controller: "frontPageController"
  ).when("/home",
    templateUrl: "templates/user_home.html"
    controller: "homeController"
    resolve:
      login: login_resolver('user')
      huser: (UserService, $rootScope) ->
        UserService.query(
          id: $rootScope.user.id
          join_prof: "home_join").$promise
  ).when("/new_project",
    templateUrl: "templates/new_project.html"
    controller: "newProjController"
    resolve:
      login: login_resolver('user')
  ).when("/signup",
    templateUrl: "templates/signup.html"
    controller: "signupController"
    resolve:
      login: login_resolver('not_user')
  ).when("/account",
    templateUrl: "templates/account.html"
    controller: "accountController"
    resolve:
      login: login_resolver('user')
      acc_user: (UserService, $rootScope) ->
        UserService.query(
          __filter_by:
            username: $rootScope.user.username
          __one: true
          join_prof: "settings_join").$promise
  ).when("/account/:subsection",
    templateUrl: "templates/account.html"
    controller: "accountController"
    resolve:
      login: login_resolver('user')
      acc_user: (UserService, $rootScope) ->
        UserService.query(
          __filter_by:
            username: $rootScope.user.username
          join_prof: "settings_join").$promise
  # Error Pages
  ).when("/errors/:error",
    templateUrl: "templates/error.html"
    controller: "errorController"
  # Primary object views
  ).when("/:username/:url_key",
    templateUrl: "templates/project.html"
    controller: "projectController"
    resolve:
      project: (ProjectService, $route) ->
        ProjectService.query(
          __filter_by:
            maintainer_username: $route.current.params.username
            url_key: $route.current.params.url_key
          join_prof: 'page_join').$promise
  ).when("/:username/:url_key/new_issue",
    templateUrl: "templates/new_issue.html"
    controller: "newIssueController"
    resolve:
      login: login_resolver('user')
      issues: (IssueService, $route) ->
        IssueService.query(
          __filter_by:
            project_maintainer_username: $route.current.params.username
            project_url_key: $route.current.params.url_key
          join_prof: 'brief_join').$promise
  ).when("/:username/:url_key/psettings",
    templateUrl: "templates/psettings.html"
    controller: "projectSettingsController"
    resolve:
      login: login_resolver('user')
      project: (ProjectService, $route) ->
        ProjectService.query(
          __filter_by:
            maintainer_username: $route.current.params.username
            url_key: $route.current.params.url_key
          __one: true
          join_prof: 'page_join').$promise
  ).when("/:username/:purl_key/:url_key",
    templateUrl: "templates/issue.html"
    controller: "issueController"
    resolve:
      issue: (IssueService, $route) ->
        IssueService.query(
          __filter_by:
            project_maintainer_username: $route.current.params.username
            project_url_key: $route.current.params.purl_key
            url_key: $route.current.params.url_key
          join_prof: "page_join").$promise
  ).when("/:username/:purl_key/:url_key/new_solution",
    templateUrl: "templates/new_solution.html"
    controller: "newSolutionController"
    resolve:
      login: login_resolver('user')
      solutions: (SolutionService, $route) ->
        SolutionService.query(
          __filter_by:
              project_maintainer_username: $route.current.params.username
              project_url_key: $route.current.params.purl_key
              issue_url_key: $route.current.params.url_key
          join_prof: 'disp_join').$promise
  ).when("/:username/:purl_key/:iurl_key/:url_key",
    templateUrl: "templates/solution.html"
    controller: "solutionController"
    resolve:
      solution: (SolutionService, $route) ->
        SolutionService.query(
          __filter_by:
            url_key: $route.current.params.url_key
            issue_url_key: $route.current.params.iurl_key
            project_url_key: $route.current.params.purl_key
            project_maintainer_username: $route.current.params.username
          __one: true
          join_prof: "page_join").$promise
  ).when("/tos",
    templateUrl: "templates/tos.html"
  # user profile
  ).when("/:username",
    templateUrl: "templates/profile.html"
    controller: "profileController"
    resolve:
      prof_user: (UserService, $route) ->
        UserService.query(
          __filter_by:
            username: $route.current.params.username
          join_prof: 'page_join'
          __one: true).$promise
  ).otherwise(
    redirectTo: "/404"
  )
]

##############################################################################
# Filters ####################################################################
mainFilters = angular.module("mainFilters", [])
mainFilters.filter('searchFilter', ($sce) ->
  trusted = {}
  (input, query, option) ->
    if input == undefined
      return
    if input
      tmp = input.replace(
        RegExp('('+ query + ')', 'gi'), '<span class="match">$1</span>')
      return trusted[tmp] || (trusted[tmp] = $sce.trustAsHtml(tmp))
    else
      return input
)
mainFilters.filter('fuseImpFilter', ->
  (input, query, option) ->
    if input == undefined
      return
    if query
      f = new Fuse(input,
        keys: ['title']
      )
      return f.search(query)
    else
      return input
)

mainFilters.filter "date_ago", ->
  (input, p_allowFuture) ->
    substitute = (stringOrFunction, number, strings) ->
      if $.isFunction(stringOrFunction)
        string = stringOrFunction(number, dateDifference)
      else
        string = stringOrFunction
      value = (strings.numbers and strings.numbers[number]) or number
      string.replace /%d/i, value

    nowTime = (new Date()).getTime()
    date = (new Date(input)).getTime()

    #refreshMillis= 6e4, //A minute
    allowFuture = p_allowFuture or false
    strings =
      prefixAgo: null
      prefixFromNow: null
      suffixAgo: "ago"
      suffixFromNow: "from now"
      seconds: "less than a minute"
      minute: "a minute"
      minutes: "%d minutes"
      hour: "an hour"
      hours: "%d hours"
      day: "a day"
      days: "%d days"
      month: "a month"
      months: "%d months"
      year: "a year"
      years: "%d years"

    dateDifference = nowTime - date
    words = undefined
    seconds = Math.abs(dateDifference) / 1000
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    years = days / 365

    # var strings = this.settings.strings;
    prefix = strings.prefixAgo
    suffix = strings.suffixAgo
    if allowFuture
      if dateDifference < 0
        prefix = strings.prefixFromNow
        suffix = strings.suffixFromNow
    words = seconds < 45 and substitute(strings.seconds, Math.round(seconds), strings) \
            or seconds < 90 and substitute(strings.minute, 1, strings) \
            or minutes < 45 and substitute(strings.minutes, Math.round(minutes), strings) \
            or minutes < 90 and substitute(strings.hour, 1, strings) \
            or hours < 24 and substitute(strings.hours, Math.round(hours), strings) \
            or hours < 42 and substitute(strings.day, 1, strings) \
            or days < 30 and substitute(strings.days, Math.round(days), strings) \
            or days < 45 and substitute(strings.month, 1, strings) \
            or days < 365 and substitute(strings.months, Math.round(days / 30), strings) \
            or years < 1.5 and substitute(strings.year, 1, strings) \
            or substitute(strings.years, Math.round(years), strings)
    $.trim [prefix, words, suffix].join(" ")


##############################################################################
# Directives #################################################################

mainApp.directive "dynamic", ($compile) ->
  replace: true
  link: (scope, ele, attrs) ->
    scope.$watch attrs.dynamic, (html) ->
      ele.html html
      $compile(ele.contents()) scope

mainApp.directive "btfMarkdown", ->
  converter = new Showdown.converter()
  restrict: "AE"
  link: (scope, element, attrs) ->
    if attrs.btfMarkdown
      scope.$watch attrs.btfMarkdown, (newVal) ->
        html = (if newVal then converter.makeHtml(newVal) else "")
        element.html html

    else
      html = converter.makeHtml(element.text())
      element.html html

mainApp.directive "markItUp", ->
  restrict: "A"
  link: (scope, element, attrs) ->
    new_settings = $.extend(window.mySettings,
      afterInsert: ->
        scope.$apply(
          element.trigger('input')
          element.trigger('change')
        )
    )
    element.markItUp(new_settings)

mainApp.directive "passwordMatch", [->
  restrict: "A"
  scope: true
  require: "ngModel"
  link: (scope, elem, attrs, control) ->
    checker = ->

      #get the value of the other password
      e2 = scope.$eval(attrs.passwordMatch).$viewValue
      control.$viewValue is e2

    scope.$watch checker, (n) ->

      #set the form control to valid if both
      #passwords are the same, else invalid
      control.$setValidity "unique", n
]

mainApp.directive "validClass", [->
  restrict: "A"
  scope: false
  link: (scope, elem, attrs, control) ->

    frm_dat = scope.$eval(attrs.validClass)
    scope.$watch( ->
      frm_dat.$valid && frm_dat.$dirty
    , (ret) ->
      if ret
        elem.addClass('has-success')
      else
        elem.removeClass('has-success')
    )
    scope.$watch( ->
      frm_dat.$invalid && frm_dat.$dirty
    , (ret) ->
      if ret
        elem.addClass('has-error')
      else
        elem.removeClass('has-error')
    )
]

mainApp.directive "uniqueServerside",
["$http", "$timeout", ($http, $timeout) ->
  require: "ngModel"
  restrict: "A"
  link: (scope, elem, attrs, ctrl) ->
    scope.busy = false
    scope.$watch attrs.ngModel, (value) ->
      # hide old error messages
      ctrl.$setValidity "taken", true

      # don't send undefined to the server during dirty check empty username is
      # caught by required directive
      return  unless value

      # show spinner
      scope.busy = true
      scope.confirmed = false

      # everything is fine -> do nothing
      $http.post(window.api_path + attrs.uniqueServerside,
        value: elem.val()
      ).success((data) ->
        $timeout ->
          # display new error message
          if data.taken
            ctrl.$setValidity "taken", false
            scope.confirmed = false
          else
            scope.confirmed = true
          scope.busy = false
        , 500
      ).error (data) ->
        scope.busy = false
]

mainApp.directive "toggleButton", ["$http", "$timeout", ($http, $compile) ->
  restrict: "A"
  link: (scope, elem, attrs, ctrl) ->
    attr = attrs.toggleButton
    icon = elem.find('i')
    text = elem.find('#text')
    scope.$watch('saving.' + attr, (val) ->
      if val
        icon.removeClass()
        icon.addClass('fa fa-spin fa-spinner')
      else
        update(scope.$eval(attr))
    )
    update = (val) ->
      if val
        icon.removeClass()
        icon.addClass('fa ' + icon.attr('on'))
        elem.addClass('active')
        text.html(text.attr('on'))
      else
        icon.removeClass()
        icon.addClass('fa ' + icon.attr('off'))
        elem.removeClass('active')
        text.html(text.attr('off'))


    scope.$watch(attr,update)
]

mainApp.directive "reportDropdown", ($http, $compile, $rootScope, $modal) ->
  templateUrl: "templates/dir/drop_toggle.html"
  restrict: "E"
  scope:
    textCls: '@'
    var: '@'
    config: '='
    varValue: '=var'
    savingVarValue: '=savingVar'
    updateFunc: '=update'
  compile: (elem, attrs, transclude) ->
    post: (scope, elem, attrs, ctrl) ->
      # set some defaults on our option config objects
      for val of scope.config.options
        scope.config.options[val] = $.extend(
          confirm: false
          confirmText: "Are you sure?"
          icon: ""
          btnCls: ""
          text: scope.config.options[val]['value']
        , scope.config.options[val])

      icon = elem.find('i')          # button icon
      text = elem.find('#text') # button text
      button = elem.find('.button')  # actual button
      # switch on the saving spinner when saving
      scope.$watch('savingVarValue', (val) ->
        if val
          icon.removeClass()
          icon.addClass('fa fa-spin fa-spinner')
        else
          update(scope.varValue)
      )

      # keep track of the classes that have been put on the button
      classes_added = ""
      # Changes the button state, button color, and text according to current
      # status
      update = (value) ->
        for key of scope.config.options
          if scope.config.options[key].value == value
            config = scope.config.options[key]
        if not config?
          throw "Current dropdown value not found in configuration list"

        icon.removeClass()
        icon.addClass(config['icon'])

        button.removeClass(classes_added)
        button.addClass(config['btnCls'])
        classes_added = config['btnCls']

        text.html(config['text'])
      scope.$watch('varValue', update)

      # called from the template. Runs specified update function from parent
      scope.change = (key) ->
        config = scope.config.options[key]
        if config.confirm
          $modal.open(
            templateUrl: "templates/confirm_modal.html"
            controller: ($scope) ->
              $scope.title = config.confirmText
          ).result.then ->
            scope.updateFunc(scope.var, config.value)
        else
          scope.updateFunc(scope.var, config.value)

