2. Edit the ``/etc/barbican/barbican.conf`` file and complete the following
   actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: none

        [database]
        ...
        connection = mysql+pymysql://barbican:BARBICAN_DBPASS@controller/barbican

     Replace ``BARBICAN_DBPASS`` with the password you chose for the
     Key Manager service database.

   * In the ``[DEFAULT]`` and ``[oslo_messaging_rabbit]`` sections,
     configure ``RabbitMQ`` message queue access:

     .. code-block:: ini

        [DEFAULT]
        ...
        rpc_backend = rabbit

        [oslo_messaging_rabbit]
        ...
        rabbit_host = controller
        rabbit_userid = openstack
        rabbit_password = RABBIT_PASS

     Replace ``RABBIT_PASS`` with the password you chose for the
     ``openstack`` account in ``RabbitMQ``.

   * In the ``[keystone_authtoken]`` section, configure Identity
     service access:

     .. code-block:: ini

        [keystone_authtoken]
        ...
        auth_uri = http://controller:5000
        auth_url = http://controller:35357
        memcached_servers = controller:11211
        auth_type = password
        project_domain_name = default
        user_domain_name = default
        project_name = service
        username = barbican
        password = BARBICAN_PASS

     Replace ``BARBICAN_PASS`` with the password you chose for the
     ``barbican`` user in the Identity service.

     .. note::

        Comment out or remove any other options in the
        ``[keystone_authtoken]`` section.

#. Edit the ``/etc/barbican/barbican-api-paste.ini`` file and complete the
   following actions:

   * In the ``[pipeline:barbican_api]`` section, configure the pipeline to
     use the Identity Service auth token.

     .. code-block:: ini

        [pipeline:barbican_api]
        pipeline = cors authtoken context apiapp

#. Populate the Key Manager service database:

   The Key Manager service database will be automatically populated
   when the service is first started.  To prevent this, and run the
   database sync manually, edit the ``/etc/barbican/barbican.conf`` file
   and set db_auto_create in the ``[DEFAULT]`` section to False.

   Then populate the database as below:

   .. code-block:: console

      $ su -s /bin/sh -c "barbican-manage db_sync" barbican

   .. note::

      Ignore any deprecation messages in this output.

#.  Barbican has a plugin architecture which allows the deployer to store secrets in
    a number of different back-end secret stores.  By default, Barbican is configured to
    store secrets in a basic file-based keystore.  This key store is NOT safe for
    production use.

    For a list of supported plugins and detailed instructions on how to configure them,
    see :ref:`barbican_backend`
