mainServices = angular.module("mainServices", ["ngResource"])
mainServices.factory("ProblemService", ($resource) ->
  $resource window.api_path + "improvement", {},
    update:
      method: "POST"
      timeout: 5000
    query:
      method: "GET"
      timeout: 5000
      isArray: true
)

mainServices.factory("UserService", ($resource) ->
  $resource window.api_path + "user", {},
    login:
      url: window.api_path + "login"
      method: "POST"
      timeout: 5000
      isArray: false
    query:
      method: "GET"
      isArray: false
)

mainServices.factory("ProjectService", ($resource) ->
  $resource window.api_path + "project", {},
    query:
      method: "GET"
      timeout: 5000
      isArray: true
)

mainServices.factory("StripeService", ($resource) ->
  $resource window.api_path + "charge", {},
    update:
      method: "POST"
      timeout: 5000
)

mainServices.factory("TransService", ($resource) ->
  $resource window.api_path + "transaction", {}
    query:
      method: "GET"
      timeout: 5000
      isArray: true
)
