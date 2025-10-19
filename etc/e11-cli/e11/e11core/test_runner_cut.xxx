    # pylint: disable=too-many-positional-arguments
    def python_entry(self, file: str, func: str, args=(), kwargs=None, timeout=DEFAULT_NET_TIMEOUT_S) -> PythonEntryResult:
        kwargs = kwargs or {}

        if self.ssh:
            # grader: run remotely using the student's Python; print JSON sentinel
            labdir = self.ctx['labdir']
            py = f"{labdir}/.venv/bin/python"
            args_js = json.dumps(list(args))
            kwargs_js = json.dumps(kwargs)
            script = f"""
        import importlib.util, json, sys
        spec = importlib.util.spec_from_file_location("student_entry", {repr(file)})
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, {repr(func)})
        val = fn(*json.loads({repr(args_js)}), **json.loads({repr(kwargs_js)}))
        print("__E11_VALUE__="+json.dumps(val))
        """
            rc, out, err = self.ssh.exec(f"{py} - <<'PY'\n{script}\nPY", timeout=timeout)
            value = None
            m = re.search(r"__E11_VALUE__=(.*)", out)
            if m:
                try:
                    value = json.loads(m.group(1))
                except Exception: # pylint: disable=broad-exception-caught
                    pass
            return PythonEntryResult(exit_code=rc, stdout=out, stderr=err, value=value)

        # local: import and call directly, capturing stdout/err
        old_out, old_err = sys.stdout, sys.stderr
        buf_out, buf_err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = buf_out, buf_err
        exit_code = 0
        value = None
        try:
            if venv and not (os.path.isdir(venv) and os.path.isfile(f"{venv}/bin/python")):
                raise RuntimeError(f"virtualenv '{venv}' not found (expected {venv}/bin/python)")
            spec = importlib.util.spec_from_file_location("student_entry", file)
            if not spec or not spec.loader:
                raise RuntimeError(f"cannot import {file}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            fn = getattr(mod, func)       # call the test function
            value = fn(*args, **kwargs)
        except SystemExit as e:
            exit_code = int(e.code) if isinstance(e.code, int) else 1
        except Exception:       # pylint: disable=broad-exception-caught
            exit_code = 1
            traceback.print_exc()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            out, err = buf_out.getvalue(), buf_err.getvalue()
            sys.stdout, sys.stderr = old_out, old_err
        return PythonEntryResult(exit_code=exit_code, stdout=out, stderr=err, value=value)
