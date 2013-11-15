mainServices = angular.module("mainServices", ["ngResource"])
mainServices.factory("ImpService", ($resource) ->
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
  $resource window.api_path + "login", {},
    update:
      method: "POST"
      timeout: 5000
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
