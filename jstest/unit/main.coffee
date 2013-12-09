"use strict"

# jasmine specs for controllers go here
describe "controllers", ->

  mockService =
    query: (x) ->
      "weee"

  beforeEach inject(($rootScope, $controller) ->

    #create a scope object for us to use.
    $scope = $rootScope.$new()

    #now run that scope through the controller function,
    #injecting any services or other injectables we need.
    ctrl = $controller("rootController",
      $scope: $scope
      $rootScope: $rootScope
      UserService: mockService
    )
  )
  it "should have default title set", inject( ($rootScope) ->
    expect($rootScope.title).toEqual('')
    expect($rootScope._title).toEqual('Crowd Link')
  )
