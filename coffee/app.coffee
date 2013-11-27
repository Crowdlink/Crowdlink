'use strict'
mainApp = angular.module("mainApp", ['mainServices', 'mainControllers', 'mainFilters', 'ngRoute', 'ngAnimate'])
# Avoid collision with Jinja templates
mainApp.config ($interpolateProvider) ->
  $interpolateProvider.startSymbol "{[{"
  $interpolateProvider.endSymbol "}]}"

mainApp.config ["$routeProvider", ($routeProvider) ->
  $routeProvider.when("/login",
    templateUrl: "templates/login.html"
    controller: "loginController"
  ).when("/logout",
    templateUrl: "main.html"
    controller: "remoteController"
  ).when("/",
    templateUrl: "templates/home.html"
    controller: "frontpageController"
  ).when("/home",
    templateUrl: "templates/user_home.html"
    controller: "homeController"
  ).when("/new_project",
    templateUrl: "templates/new_project.html"
    controller: "newProjController"
  ).when("/signup",
    templateUrl: "templates/signup.html"
    controller: "signupController"
  ).when("/account",
    templateUrl: "templates/account.html"
    controller: "accountController"
  ).when("/account/:subsection",
    templateUrl: "templates/account.html"
    controller: "accountController"
  ).when("/:username/:url_key",
    templateUrl: "templates/project.html"
    controller: "projectController"
  ).when("/:username/:url_key/new_issue",
    templateUrl: "templates/new_issue.html"
    controller: "newissueController"
  ).when("/:username/:url_key/psettings",
    templateUrl: "templates/psettings.html"
    controller: "projectSettingsController"
  ).when("/:username/:purl_key/:url_key",
    templateUrl: "templates/issue.html"
    controller: "issueController"
  ).when("/:username",
    templateUrl: "templates/profile.html"
    controller: "profileController"
  ).otherwise(
    templateUrl: "templates/404.html"
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
      tmp = input.replace(RegExp('('+ query + ')', 'gi'), '<span class="match">$1</span>')
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
      string = (if $.isFunction(stringOrFunction) then stringOrFunction(number, dateDifference) else stringOrFunction)
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
      minute: "about a minute"
      minutes: "%d minutes"
      hour: "about an hour"
      hours: "about %d hours"
      day: "a day"
      days: "%d days"
      month: "about a month"
      months: "%d months"
      year: "about a year"
      years: "%d years"

    dateDifference = nowTime - date
    words = undefined
    seconds = Math.abs(dateDifference) / 1000
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    years = days / 365
    separator = (if strings.wordSeparator is `undefined` then " " else strings.wordSeparator)

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
    $.trim [prefix, words, suffix].join(separator)


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
    new_settings = $.extend(mySettings,
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

mainApp.directive "uniqueServerside", ["$http", "$timeout", ($http, $timeout) ->
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
