mainControllers = angular.module("mainControllers", [])

# RootController ==============================================================
mainControllers.controller('rootController',
  ($scope, $location, $rootScope)->
    $scope.init = (logged_in, curr_username) ->
      $rootScope.logged_in = logged_in
      $rootScope.curr_username = curr_username

    # update the profile url when the username changes
    $rootScope.$watch('curr_username', ->
      $scope.profile = '/u/' + $rootScope.curr_username
    )

    $rootScope.location = $location
    $rootScope.strings =
      err_comm = "Error communicating with server."
)
# EditController ==============================================================
mainControllers.controller('problemEditController',
  ($scope, $timeout, ImpService)->
    $scope.init = (id, brief, desc_md, desc, status, close_reason) ->
        $scope.id = id
        $scope.brief = brief
        # data type edit templates
        $scope.brief =
          val: unescape(brief)
          editing: false
          saving: false
          prev: ""
        $scope.desc =
          val: unescape(desc)
          md: unescape(desc_md)
          editing: false
          saving: false
          prev: ""
        # toggle type templates
        $scope.status =
          val: status == 'True'
          saving: false
        # toggle type templates
        $scope.close_reason =
          val: close_reason
          saving: false

    $scope.revert = (s) ->
        s.val = s.prev
        $scope.toggle(s)

    $scope.save = (s, callback) ->
        s.saving = true
        ImpService.update(
            brief: $scope.brief.val
            description: $scope.desc.val
            open: $scope.status.send_val
            render_md: true
            id: $scope.id
        ,(value) -> # Function to be run when function returns
            if value.success
                $scope.desc.md = value.md
                $timeout ->
                    if callback
                      callback()
                    s.saving = false
                    s.editing = false
                , 1000
            else
                if 'message' of value
                    text = "Error communicating with server. #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{value.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
                s.saving = false
        )

    $scope.swap_save = (s) ->
      s.send_val = !s.val
      $scope.save(s, ->
        s.val = !s.val
      )

    $scope.toggle = (s) ->
        s.prev = s.val
        s.editing = !s.editing
)

# RemoteController ============================================================
mainControllers.controller('remoteController', ($scope, $rootScope, $routeParams, $location, $http, $sce)->
  $scope.init = () ->
    loc = $location.path()
    # this catch feels sketchy because it causes infinite loop if it doesn't work.
    # should probably switch at some point XXX
    if loc == "/" or loc == ""
      loc = "/home"

    console.log(loc)
    $http.get(loc).success((data, status, headers, config) ->
      if "application/json" == headers('Content-Type')
        if 'access_denied' of data
          $rootScope.logged_in = false
          $rootScope.curr_username = undefined
          $location.path("/login")
          console.log("Logging out!")
      else
        $scope.html_out = data
    )

)

# LoginController ============================================================
mainControllers.controller('loginController', ($scope, $rootScope, UserService, $location)->
  $scope.submit = () ->
    $scope.errors = []
    UserService.update(
        username: $scope.username
        password: $scope.password
    ,(value) ->
        if 'success' of value and value.success
          $rootScope.logged_in = true
          $rootScope.curr_username = $scope.username
          $location.path("/")
        else
          if 'message' of value
            $scope.errors = [value.message, ]
          else
            $scope.errors = [value.message, ]
      )
)

# ProjectSearch ===============================================================
mainControllers.controller('projectSearch',
['$scope', '$timeout', 'ImpService',
  ($scope, $timeout, ImpService)->
    $scope.init = (project, imps) ->
        $scope.project = project
        $scope.imps = JSON.parse(unescape(imps))

    $scope.search = ->
        $scope.saving = true
        ImpService.query(
            filter: $scope.filter
            project: $scope.project
        ,(value) -> # Function to be run when function returns
            if 'success' not of value
                $timeout ->
                    $scope.imps = value
                , 100
            else
                if 'message' of value
                    text = " #{value.message}"
                else
                    text = "There was an unknown error committing your action. #{value.code}"
                noty
                    text: text
                    type: 'error'
                    timout: 2000
        )

    $scope.vote = (imp) ->
      imp.vote_status = !imp.vote_status
      if imp.vote_status
        imp.votes += 1
      else
        imp.votes -= 1

])

# ChargeController ============================================================
mainControllers.controller('chargeController', ['$scope', 'StripeService', ($scope, StripeService)->
    $scope.init = (sk, userid) ->
      window.handler = StripeCheckout.configure
        token: $scope.recv_token
        key: sk
      $scope.amount = 500
      $scope.userid = userid
      $scope.result =
        text: ""
        type: ""
        show: false

    $scope.recv_token = (token, args) ->
      console.log(args)
      StripeService.update(
          token: token
          amount: $scope.amount
          userid: $scope.userid
      ,(value) -> # Function to be run when function returns
          $scope.result =
            text: "You're card has been successfully charged"
            type: "success"
            show: true
      )

    $scope.pay = () ->
      # Open Checkout with further options
      handler.open
        image: window.static_path + "/img/logo_stripe.png"
        name: "Featurelet"
        description: "Credits ($" + $scope.amount/100 + ")"
        amount: $scope.amount
])

# TransactionController =======================================================
mainControllers.controller('transactionsController', ['$scope', 'StripeService', ($scope, StripeService)->
    $scope.init = (transactions) ->
      $scope.transactions = JSON.parse(unescape(transactions))
      for trans in $scope.transactions
        trans.details = false
])
