from core.libs import *
from core.visualization import *
from core.utils import Logger, Manager


class Propagator:
    def __init__(self, **kwargs):
        self.global_root_dir = kwargs["global_root_dir"]
        self.beam = kwargs["beam"]

        self.diffraction = kwargs.get("diffraction", None)
        self.kerr_effect = kwargs.get("kerr_effect", None)

        self.manager = Manager(global_root_dir=self.global_root_dir)
        self.logger = Logger(diffraction=self.diffraction,
                             kerr_effect=self.kerr_effect,
                             path=self.manager.results_dir)

        self.n_z = kwargs["n_z"]
        self.flag_const_dz = kwargs["flag_const_dz"]

        self.dn_print_current_state = kwargs.get("dn_print_current_state", None)
        self.flag_print_beam = True if self.dn_print_current_state else False

        self.dn_plot_beam = kwargs.get("dn_plot_beam", None)
        self.flag_print_track = True if self.dn_plot_beam else False
        if self.dn_plot_beam:
            self.plot_beam_normalization = kwargs["plot_beam_normalization"]

        self.z = 0.0
        self.dz = kwargs["dz0"]

        self.states_columns = ["z, m", "dz, m", "i_max / i_0", "i_max, W / m^2"]
        self.states_arr = np.zeros(shape=(self.n_z + 1, 4))

    @staticmethod
    @jit(nopython=True)
    def flush_current_state(states_arr, n_step, z, dz, i_max, i_0):
        states_arr[n_step][0] = z
        states_arr[n_step][1] = dz
        states_arr[n_step][2] = i_max
        states_arr[n_step][3] = i_max * i_0

    @staticmethod
    @jit(nopython=True)
    def update_dz(k_0, n_0, n_2, i_max, i_0, dz, nonlin_phase_max=0.05):
        nonlin_phase = k_0 * n_2 * i_0 * i_max * dz / n_0
        if nonlin_phase > nonlin_phase_max:
            dz *= 0.8 * nonlin_phase_max / nonlin_phase

        return dz

    def crop_states_arr(self):
        row_max = 0
        for i in range(self.states_arr.shape[0] - 1, 0, -1):
            if self.states_arr[i][0] != 0 and \
                    self.states_arr[i][1] != 0 and \
                    self.states_arr[i][2] != 0 and \
                    self.states_arr[i][3] != 0:
                row_max = i + 1
                break

        self.states_arr = self.states_arr[:row_max, :]

    def propagate(self):
        t_diffraction, t_kerr, t_flush, t_plot_beam, t_logger = 0, 0, 0, 0, 0

        start = time()

        self.manager.create_global_results_dir()
        self.manager.create_results_dir()
        self.manager.create_track_dir()
        self.manager.create_beam_dir()

        self.logger.save_initial_parameters(self.beam)

        for n_step in range(int(self.n_z) + 1):
            if n_step:
                t_start = time()
                if self.diffraction:
                    self.diffraction.process(self.dz)
                t_end = time()
                t_diffraction += t_end - t_start

                t_start = time()
                if self.kerr_effect:
                    self.kerr_effect.process(self.dz)
                t_end = time()
                t_kerr = t_end - t_start

                self.beam.update_intensity()

                self.z += self.dz

                if not self.flag_const_dz:
                    self.dz = self.update_dz(self.beam.medium.k_0, self.beam.medium.n_0, self.beam.medium.n_2, self.beam.i_max, self.beam.i_0, self.dz)

            t_start = time()
            self.flush_current_state(self.states_arr, n_step, self.z, self.dz,
                                     self.beam.i_max, self.beam.i_0)
            t_end = time()
            t_flush += t_end - t_start

            t_start = time()
            if not n_step % self.dn_print_current_state:
                self.logger.print_current_state(n_step, self.states_arr, self.states_columns)
            t_end = time()
            t_logger += t_end - t_start

            t_start = time()
            if (not (n_step % self.dn_plot_beam)) and self.flag_print_beam:
                plot_beam(self.beam, self.z, n_step, self.manager.beam_dir, self.plot_beam_normalization)
            t_end = time()
            t_plot_beam += t_end - t_start

            if (self.beam.i_max > 100):
                break

        self.crop_states_arr()
        self.logger.log_track(self.states_arr, self.states_columns)

        if self.flag_print_track:
            parameter_index = self.states_columns.index("i_max / i_0")
            plot_track(self.states_arr, parameter_index,
                        self.manager.track_dir)
        end = time()

        print("diffraction = %.02f s" % (t_diffraction))
        print("kerr = %.02f s" % (t_kerr))
        print("pandas = %.02f s" % (t_flush))
        print("plot_beam = %.02f s" % (t_plot_beam))
        print("logger = %.02f s" % (t_logger))

        print("\ntime = %.02f s" % (end-start))
