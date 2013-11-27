project="crowdlink"
branch=`git rev-parse --abbrev-ref HEAD`
image="$project-$branch"

# clone in our docker configuration for the project
cd docker
docker rmi $imagee  # attempt a delete of the old image
docker stop `cat ../cid`
docker rm `cat ../cid`  # also delete the old container
# build and force a full package rebuild
docker build -no-cache -rm -t="$image" .
# a goofy way to detect if the image has been built or not. error codes
# from build don't reflect successful image creation
python -c "import commands; tmp=commands.getoutput('docker inspect $image'); ext = 0 if 'such image' not in tmp else 1; exit(ext);"
if [ $? != 0 ]; then
    # some kind of failure occured, so run our cleanup script
    /home/jenkins/bin/docker-remove-untagged
else
    # do the one time setup by invoking directly
    rm -f tmp
    docker run -cidfile="tmp" -dns="192.168.1.1" $image
    # Now commit that, and reset the command to something that will wait forever, holding open other processes
    docker commit -run="{\"Cmd\": [\"/srv/$project/start.sh\", \"true\"], \"PortSpecs\" : [\"22\", \"80\"]}" `cat tmp` $image
    docker rm `cat tmp`  # remove our orphaned container
    cd ../
    cid=`docker run -d -dns="192.168.125.1" "$image"`
    echo "$cid" > cid
    # export configs for the nginx config
    export port=`docker port $cid 80`
    export image
    # populate vars and place in nginx lookup path
    perl -p -e 's/\$\{([^}]+)\}/defined $ENV{$1} ? $ENV{$1} : $&/eg' ci/nginx.conf > nginx.conf
    sudo service nginx reload
fi
