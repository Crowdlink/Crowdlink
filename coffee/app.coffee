'use strict'
mainApp = angular.module("mainApp", ['mainServices', 'mainControllers', 'mainFilters', 'ngRoute'])
# Avoid collision with Jinja templates
mainApp.config ($interpolateProvider) ->
  $interpolateProvider.startSymbol "{[{"
  $interpolateProvider.endSymbol "}]}"

mainApp.config ["$routeProvider", ($routeProvider) ->
  $routeProvider.when("/login",
    templateUrl: "templates/login.html"
    controller: "loginController"
  ).when("/:username/:url_key",
    templateUrl: "templates/project.html"
    controller: "projectController"
  ).when("/:username/:purl_key/:url_key",
    templateUrl: "templates/improvement.html"
    controller: "problemController"
  ).otherwise(
    templateUrl: "main.html"
    controller: "remoteController"
  )
]

##############################################################################
# Filters ####################################################################
mainFilters = angular.module("mainFilters", [])
mainFilters.filter('searchFilter', ($sce) ->
  (input, query, option) ->
    input = input.replace(RegExp('('+ query + ')', 'gi'), '<span class="match">$1</span>')
    $sce.trustAsHtml(input)
)
mainFilters.filter('impFilter', ->
  (input, query, option) ->
    if query in input.brief or query in input.description
        return true
    else
        return false
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