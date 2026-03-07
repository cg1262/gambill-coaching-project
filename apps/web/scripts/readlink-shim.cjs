const fs = require("fs");

function normalize(err) {
  if (err && err.code === "EISDIR") {
    err.code = "EINVAL";
    err.message = String(err.message || "").replace(/^EISDIR/, "EINVAL");
  }
  return err;
}

const readlink = fs.readlink.bind(fs);
fs.readlink = (path, options, cb) => {
  if (typeof options === "function") {
    cb = options;
    options = undefined;
  }
  return readlink(path, options, (err, val) => (err ? cb(normalize(err)) : cb(null, val)));
};

const readlinkSync = fs.readlinkSync.bind(fs);
fs.readlinkSync = (path, options) => {
  try {
    return readlinkSync(path, options);
  } catch (err) {
    throw normalize(err);
  }
};

const readlinkPromise = fs.promises.readlink.bind(fs.promises);
fs.promises.readlink = async (path, options) => {
  try {
    return await readlinkPromise(path, options);
  } catch (err) {
    throw normalize(err);
  }
};
