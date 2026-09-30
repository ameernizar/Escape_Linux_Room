FROM alpine:3.20
RUN addgroup -S player && adduser -S -G player -h /home/player player \
  && apk add --no-cache bash coreutils findutils grep file xxd \
  && mkdir -p /escape && chown -R player:player /escape /home/player
USER player
WORKDIR /home/player
CMD ["/bin/bash", "--noprofile", "--norc"]
