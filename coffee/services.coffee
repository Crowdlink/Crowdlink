mainServices = angular.module("mainServices", ["ngResource"])


mainServices.factory("EmailService2", ($resource) ->
  $resource "{{ api_path }}email_list", {},
    create:
      method: "PATCH"
      timeout: 10000
)
