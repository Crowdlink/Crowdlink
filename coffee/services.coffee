mainServices = angular.module("mainServices", ["ngResource"])
mainServices.factory("IssueService", ($resource) ->
  $resource window.api_path + "issue", {},
    update:
      method: "POST"
      timeout: 10000
    query:
      method: "GET"
      timeout: 10000
      isArray: true
)

mainServices.factory("UserService", ($resource) ->
  $resource window.api_path + "user", {},
    login:
      url: window.api_path + "login"
      method: "POST"
      timeout: 10000
      isArray: false
    register:
      url: window.api_path + "register"
      method: "POST"
      timeout: 10000
    query:
      method: "GET"
      isArray: false
)

mainServices.factory("ProjectService", ($resource) ->
  $resource window.api_path + "project", {},
    query:
      method: "GET"
      timeout: 10000
      isArray: true
    update:
      method: "POST"
      timeout: 10000
)

mainServices.factory("StripeService", ($resource) ->
  $resource window.api_path + "charge", {},
    update:
      method: "POST"
      timeout: 10000
)

mainServices.factory("TransService", ($resource) ->
  $resource window.api_path + "transaction",
    query:
      method: "GET"
      timeout: 10000
      isArray: true
)
