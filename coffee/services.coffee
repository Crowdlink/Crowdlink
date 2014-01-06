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
    action:
      method: "PATCH"
      timeout: 10000
      isArray: false
    create:
      method: "POST"
      timeout: 10000
    query:
      method: "GET"
      isArray: false
    update:
      method: "PUT"
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

mainServices.factory("CommentService", ($resource) ->
  $resource "{{ api_path }}comment", {},
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

mainServices.factory("ChargeService", ($resource) ->
  $resource "{{ api_path }}charge", {},
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

mainServices.factory("OAuthService", ($resource) ->
  $resource "{{ api_path }}oauth", {},
    query:
      method: "GET"
      timeout: 10000
      isArray: false
)
