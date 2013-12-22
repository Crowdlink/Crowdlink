mainServices = angular.module("mainServices", ["ngResource"])
mainServices.factory("IssueService", ($resource) ->
  $resource "{{ api_path }}issue", {},
    update:
      method: "PUT"
      timeout: 10000
    create:
      method: "POST"
      timeout: 10000
    query:
      method: "GET"
      timeout: 10000
      isArray: false
)

mainServices.factory("SolutionService", ($resource) ->
  $resource "{{ api_path }}solution", {},
    update:
      method: "PUT"
      timeout: 10000
    create:
      method: "POST"
      timeout: 10000
    query:
      method: "GET"
      timeout: 10000
      isArray: false
)

mainServices.factory("UserService", ($resource) ->
  $resource "{{ api_path }}user", {},
    login:
      url: "login"
      method: "POST"
      timeout: 10000
      isArray: false
    register:
      url: "register"
      method: "POST"
      timeout: 10000
    query:
      method: "GET"
      isArray: false
)

mainServices.factory("ProjectService", ($resource) ->
  $resource "{{ api_path }}project", {},
    query:
      method: "GET"
      timeout: 10000
      isArray: false
    update:
      method: "PUT"
      timeout: 10000
    create:
      method: "POST"
      timeout: 10000
)

mainServices.factory("StripeService", ($resource) ->
  $resource "{{ api_path }}charge", {},
    update:
      method: "POST"
      timeout: 10000
)

mainServices.factory("ChargeService", ($resource) ->
  $resource "{{ api_path }}charge", {},
    query:
      method: "GET"
      timeout: 10000
      isArray: false
)
